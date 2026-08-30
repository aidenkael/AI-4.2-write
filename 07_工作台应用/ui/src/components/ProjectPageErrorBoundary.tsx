import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  pageKey: string
  children: ReactNode
}

interface State {
  error: Error | null
}

/** 只隔离项目内容；顶栏和全局导航始终保持可用。 */
export class ProjectPageErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[project-page-runtime]', error, info.componentStack)
  }

  componentDidUpdate(previous: Props): void {
    if (previous.pageKey !== this.props.pageKey && this.state.error) this.setState({ error: null })
  }

  private retry = () => this.setState({ error: null })

  render() {
    if (this.state.error) {
      return <section className="panel project-page-error" role="alert"><p>这个页面加载失败，请刷新后重试。</p><button onClick={this.retry}>重新加载页面</button></section>
    }
    return this.props.children
  }
}
