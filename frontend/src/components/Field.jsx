export function Field({ label, required, error, hint, children }) {
  return (
    <label className="field">
      <span className="field__label">
        {label}
        {required ? (
          <span className="field__required" aria-hidden="true">
            *
          </span>
        ) : null}
      </span>
      {children}
      {hint ? <span className="field__hint">{hint}</span> : null}
      {error ? (
        <span className="field__error" role="alert">
          {error}
        </span>
      ) : null}
    </label>
  )
}

export function FormActions({ onCancel, cancelLabel = 'Cancel', children }) {
  return (
    <div className="form-actions">
      {onCancel ? (
        <button type="button" className="button button--secondary" onClick={onCancel}>
          {cancelLabel}
        </button>
      ) : null}
      {children}
    </div>
  )
}