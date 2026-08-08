# -*- coding: utf-8 -*-
"""
epub_collection_split.py — 把“合集型”原始 EPUB 拆分为真正独立的单书 EPUB（Local Only）。

设计原则（对照本次架构校正）：
- 只读解析原始合集，绝不修改 / 覆盖 / 删除原合集。
- 以 EPUB 自身结构为第一依据：NCX 顶层作品节点 + OPF spine 顺序决定每部作品的边界。
  严禁用 LLM 猜测章节边界。
- 每部拆出的 EPUB 必须是真正独立的 EPUB：container.xml / OPF / manifest / spine / nav(NCX)
  均只含该作品内容，不混入前后作品正文，必需图片 / CSS 不缺失。
- 拆出的单书 EPUB 与 Local Only 拆分 manifest 都放在同一物理“合集容器”目录内；
  原始合集也保留在该目录内（按 目录规范 要求，一个合集只占一个物理目录名额）。
- 已存在的逻辑作品（如 book_0035 长安十二时辰）通过 manifest 映射为“新增来源版本”，
  不会新建 book ID，也不会改动原独立来源。

用法：
  python epub_collection_split.py --plan          # 只打印拆分计划，不写文件
  python epub_collection_split.py                 # 执行拆分（写 EPUB + manifest）
"""
from __future__ import annotations
import argparse, hashlib, json, re, sys, uuid, zipfile, posixpath
import xml.etree.ElementTree as ET
from pathlib import Path

SRC = r"C:\Users\THUNDEROBOT\Desktop\小说素材\马伯庸作品合集(畅销书《长安十二时辰》作者马伯庸经典作品全收录，套装23册，含全新长篇历史小说《两京十五日》) (马伯庸) (z-library.sk, 1lib.sk, z-lib.sk).epub"
OUT_DIR = r"E:\AI-Write\01_原始素材\02_中文文学\马伯庸作品合集"
ORIG_NAME = "马伯庸作品合集（原始23册）.epub"
CONTAINER = "马伯庸作品合集"
CATEGORY = "02_中文文学"
MANIFEST_NAME = "collection_manifest.json"
NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"
OPF_NS = "http://www.idpf.org/2007/opf"
DC_NS = "http://purl.org/dc/elements/1.1/"

# 已存在逻辑作品 → 复用其 book ID（不新建）
EXISTING_WORKS = {
    "长安十二时辰": "book_0035",   # ncx 标题可能是 “长安十二时辰（全2册）”
}
START_NEW_ID = 96  # 当前 CSV 最大为 book_0095，新作品从 96 起

REF_RE = re.compile(r'(?:src|xlink:href|href)\s*=\s*["\']([^"\']+)["\']', re.I)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def local(tag: str) -> str:
    return tag.split("}")[-1]


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def resolve_ref(base_dir: str, ref: str) -> str | None:
    ref = ref.split("#")[0].split("?")[0]
    if not ref:
        return None
    if ref.startswith("/"):
        joined = ref.lstrip("/")
    else:
        joined = posixpath.normpath(posixpath.join(base_dir, ref))
    return joined


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--plan", action="store_true", help="只打印计划，不写文件")
    args = ap.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    if not src.exists():
        print(f"ERROR 原始合集不存在：{src}", file=sys.stderr)
        return 2

    with zipfile.ZipFile(src) as z:
        names = set(z.namelist())
        # ---- OPF ----
        cont = ET.fromstring(z.read("META-INF/container.xml"))
        opf_path = None
        for el in cont.iter():
            if local(el.tag) == "rootfile":
                opf_path = el.attrib.get("full-path")
        opf = ET.fromstring(z.read(opf_path))
        manifest = {}  # id -> (href, media_type, props)
        cover_id = None
        for it in opf.iter():
            if local(it.tag) == "item":
                iid = it.attrib.get("id"); href = it.attrib.get("href")
                mt = (it.attrib.get("media-type") or "").lower()
                props = (it.attrib.get("properties") or "").lower()
                if iid and href:
                    manifest[iid] = (href, mt, props)
            elif local(it.tag) == "meta" and (it.attrib.get("name") or "").lower() == "cover":
                cover_id = it.attrib.get("content")
        spine = [it.attrib.get("idref") for it in opf.iter() if local(it.tag) == "itemref"]
        href_by_index = [manifest[s][0] for s in spine if s in manifest]
        href_set = set(href_by_index)
        # href -> id map
        href_to_id = {href: iid for iid, (href, _, _) in manifest.items()}
        # media_type by href
        mt_by_href = {href: mt for _, (href, mt, _) in manifest.items()}

        # cover image href
        cover_href = manifest.get(cover_id, (None, None, None))[0] if cover_id else None

        # ---- NCX: depth-1 book navPoints ----
        ncx = ET.fromstring(z.read("toc.ncx"))
        navmap = next(e for e in ncx.iter() if local(e.tag) == "navMap")
        books = []
        for np in list(navmap):
            if local(np.tag) != "navPoint":
                continue
            text = ""; src_ref = ""
            for c in np:
                if local(c.tag) == "navLabel":
                    for cc in c:
                        if local(cc.tag) == "text":
                            text = (cc.text or "").strip()
                elif local(c.tag) == "content":
                    src_ref = c.attrib.get("src", "")
            if not text or not src_ref:
                continue
            if text == CONTAINER or text == "总目录":
                continue
            books.append({"title": text, "src": src_ref, "elem": np})
        # sort by spine start index
        def spine_idx(src_ref):
            base = src_ref.split("#")[0]
            try:
                return href_by_index.index(base)
            except ValueError:
                return 10 ** 9
        books.sort(key=lambda b: spine_idx(b["src"]))
        # ranges
        starts = [spine_idx(b["src"]) for b in books]
        ends = starts[1:] + [len(href_by_index)]

        # ---- assign book ids ----
        new_id = START_NEW_ID
        plan = []
        for i, b in enumerate(books):
            title = b["title"]
            csv_name = title
            book_id = None
            for key, bid in EXISTING_WORKS.items():
                if title.startswith(key):
                    book_id = bid
                    csv_name = key
                    break
            if book_id is None:
                book_id = f"book_{new_id:04d}"
                new_id += 1
            plan.append({
                "index": i + 1,
                "book_id": book_id,
                "work_name": csv_name,
                "ncx_title": title,
                "author": "马伯庸",
                "spine_start": href_by_index[starts[i]],
                "spine_end": href_by_index[ends[i] - 1] if ends[i] > starts[i] else href_by_index[starts[i]],
                "content_hrefs": href_by_index[starts[i]:ends[i]],
                "is_existing": book_id in EXISTING_WORKS.values(),
                "elem": b["elem"],
            })

    # ---- plan output ----
    print(f"原始合集：{src.name}")
    print(f"识别独立作品数：{len(plan)}")
    total_content = sum(len(p["content_hrefs"]) for p in plan)
    print(f"内容文件总数（应 = spine 长度 - 2 非作品页）：{total_content}  (spine={len(href_by_index)})")
    print(f"{'#':>2}  {'book_id':<10} {'作品名':<22} {'ncx标题':<28} {'起':<20} {'止':<20} 文件数")
    for p in plan:
        print(f"{p['index']:>2}  {p['book_id']:<10} {p['work_name']:<22} {p['ncx_title'][:26]:<28} "
              f"{p['spine_start'][:18]:<20} {p['spine_end'][:18]:<20} {len(p['content_hrefs'])}")

    if args.plan:
        return 0

    # ---- execute ----
    z = zipfile.ZipFile(src)  # 重新打开（解析用的 with 已关闭）
    out.mkdir(parents=True, exist_ok=True)
    # 1) copy original into container dir (preserve)
    orig_bytes = src.read_bytes()
    (out / ORIG_NAME).write_bytes(orig_bytes)
    orig_sha = sha256_bytes(orig_bytes)
    orig_size = len(orig_bytes)

    splits_meta = []
    for p in plan:
        hrefs = p["content_hrefs"]
        # resolve referenced resources from content files
        included_ids = set()
        for href in hrefs:
            base_dir = posixpath.dirname(href)
            data = z.read(href).decode("utf-8", "replace")
            for m in REF_RE.finditer(data):
                r = resolve_ref(base_dir, m.group(1))
                if r and r in href_to_id:
                    included_ids.add(href_to_id[r])
        # always include css + cover
        for iid, (href, mt, _) in manifest.items():
            if mt == "text/css":
                included_ids.add(iid)
        if cover_href and cover_href in href_to_id:
            included_ids.add(href_to_id[cover_href])

        # included href sets: content (always) + referenced resources
        content_ids = [href_to_id[h] for h in hrefs]
        # 资源只取非正文文件（图片 / CSS / 封面等），避免把其他书的正文 xhtml 当作资源混入
        resource_ids = [iid for iid in included_ids
                        if iid not in content_ids
                        and manifest[iid][1] != "application/xhtml+xml"]
        all_ids = content_ids + resource_ids

        # build OPF
        uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, "ai-write." + p["book_id"]))
        items_xml = []
        itemrefs_xml = []
        chap_n = 0
        for iid in content_ids:
            chap_n += 1
            href = manifest[iid][0]
            items_xml.append(f'    <item id="chap{chap_n:03d}" href="{esc(href)}" media-type="application/xhtml+xml"/>')
            itemrefs_xml.append(f'    <itemref idref="chap{chap_n:03d}"/>')
        for iid in resource_ids:
            href, mt, _ = manifest[iid]
            items_xml.append(f'    <item id="res_{iid}" href="{esc(href)}" media-type="{esc(mt)}"/>')
        opf_xml = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="{OPF_NS}" version="2.0" unique-identifier="bookid" xmlns:dc="{DC_NS}">
  <metadata>
    <dc:identifier id="bookid">urn:uuid:{uid}</dc:identifier>
    <dc:title>{esc(p["work_name"])}</dc:title>
    <dc:creator>{esc(p["author"])}</dc:creator>
    <dc:language>zh</dc:language>
    <dc:publisher>马伯庸作品合集（拆分来源）</dc:publisher>
  </metadata>
  <manifest>
{chr(10).join(items_xml)}
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
  </manifest>
  <spine toc="ncx">
{chr(10).join(itemrefs_xml)}
  </spine>
</package>
'''
        # build NCX from original subtree (filter uses THIS book's own content set)
        subtree = rewrite_navpoint(p["elem"], set(hrefs))
        subtree_xml = ET.tostring(subtree, encoding="unicode")
        subtree_xml = subtree_xml.replace(f' xmlns="{NCX_NS}"', "")
        ncx_xml = f'''<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="{NCX_NS}" version="2005-1">
  <head>
    <meta name="dtb:uid" content="{uid}"/>
    <meta name="dtb:depth" content="2"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{esc(p["work_name"])}</text></docTitle>
  <docAuthor><text>{esc(p["author"])}</text></docAuthor>
  <navMap>
{subtree_xml}
  </navMap>
</ncx>
'''
        container_xml = '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
'''
        epub_name = f"{p['ncx_title']}.epub"
        epub_path = out / epub_name
        with zipfile.ZipFile(epub_path, "w", zipfile.ZIP_DEFLATED) as zo:
            zi = zipfile.ZipInfo("mimetype")
            zi.compress_type = zipfile.ZIP_STORED
            zi.external_attr = 0o644 << 16
            zo.writestr(zi, "application/epub+zip")
            zo.writestr("META-INF/container.xml", container_xml)
            zo.writestr("content.opf", opf_xml.encode("utf-8"))
            zo.writestr("toc.ncx", ncx_xml.encode("utf-8"))
            for iid in all_ids:
                href = manifest[iid][0]
                if href in names:
                    zo.writestr(href, z.read(href))
        data = epub_path.read_bytes()
        splits_meta.append({
            "index": p["index"],
            "book_id": p["book_id"],
            "work_name": p["work_name"],
            "ncx_title": p["ncx_title"],
            "author": p["author"],
            "filename": epub_name,
            "size": len(data),
            "sha256": sha256_bytes(data),
            "content_files": len(hrefs),
            "spine_start": p["spine_start"],
            "spine_end": p["spine_end"],
            "is_existing_work": p["is_existing"],
        })
        print(f"  写出 {epub_name}  [{p['book_id']}]  {len(data)} bytes, {len(hrefs)} 文件")

    manifest_obj = {
        "schema_version": "1.0",
        "container": CONTAINER,
        "container_dir": f"{CATEGORY}/{CONTAINER}",
        "category": CATEGORY,
        "source_format": "epub",
        "split_basis": "EPUB 自身 NCX 顶层作品节点 + OPF spine 顺序；非 LLM 猜测章节。",
        "original": {
            "filename": ORIG_NAME,
            "size": orig_size,
            "sha256": orig_sha,
            "opf_title": None,
            "opf_creator": None,
            "manifest_count": 0,
            "spine_count": 0,
        },
        "note": "原合集永久保留；本 manifest 为 Local Only，不上传 GitHub。",
        "splits": splits_meta,
    }
    # fill original opf title/creator cleanly
    with zipfile.ZipFile(src) as z:
        o = ET.fromstring(z.read("content.opf"))
        t = next((e.text for e in o.iter() if local(e.tag) == "title" and e.text), None)
        c = next((e.text for e in o.iter() if local(e.tag) == "creator" and e.text), None)
    manifest_obj["original"]["opf_title"] = t
    manifest_obj["original"]["opf_creator"] = c
    manifest_obj["original"]["manifest_count"] = len(manifest)
    manifest_obj["original"]["spine_count"] = len(href_by_index)

    (out / MANIFEST_NAME).write_text(json.dumps(manifest_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成：{len(splits_meta)} 本独立 EPUB + manifest")
    print(f"原始合集保留：{out / ORIG_NAME}  (sha256={orig_sha[:16]}...)")
    return 0


def rewrite_navpoint(elem, href_set, counter=None):
    """深拷贝 navPoint 子树，重排 id，并过滤掉指向本书内容范围之外文件的节点。"""
    if counter is None:
        counter = [0]
    tag = local(elem.tag)
    if tag != "navPoint":
        # copy other elements (navLabel/text/content) as-is
        new = ET.Element(elem.tag, dict(elem.attrib))
        new.text = elem.text
        new.tail = elem.tail
        for child in elem:
            new.append(rewrite_navpoint(child, href_set, counter))
        return new
    # navPoint
    counter[0] += 1
    nid = f"np{counter[0]:03d}"
    new = ET.Element("{%s}navPoint" % NCX_NS, {"id": nid, "class": elem.attrib.get("class", "chapter")})
    new.text = elem.text
    new.tail = elem.tail
    child_navpoints = 0
    for child in elem:
        if local(child.tag) == "navPoint":
            sub = rewrite_navpoint(child, href_set, counter)
            # filter: only keep if its content src file is in this book's content set
            src = None
            for cc in sub.iter():
                if local(cc.tag) == "content":
                    src = (cc.attrib.get("src") or "").split("#")[0]
            if src and src in href_set:
                new.append(sub)
                child_navpoints += 1
            # else drop (cross-book reference)
        else:
            new.append(rewrite_navpoint(child, href_set, counter))
    return new


if __name__ == "__main__":
    raise SystemExit(main())
