export function LoadingState({ children = 'Loading…' }) {
  return <div className="state state--loading">{children}</div>
}

export function EmptyState({ title, children }) {
  return (
    <div className="state state--empty">
      <p className="state__title">{title}</p>
      {children}
    </div>
  )
}

export function ErrorState({ title, message, children }) {
  return (
    <div className="state state--error" role="alert">
      <p className="state__title">{title}</p>
      {message ? <p className="state__message">{message}</p> : null}
      {children}
    </div>
  )
}