import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="section container prose">
      <h1 className="page-title">Page not found</h1>
      <p>That page doesn't exist.</p>
      <p><Link to="/" className="button button-primary">Back to home</Link></p>
    </div>
  )
}
