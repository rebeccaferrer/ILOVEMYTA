import { Link } from 'react-router-dom'

export default function AboutPage() {
  return (
    <div className="section container prose">
      <h1 className="page-title">About Us</h1>
      <p>
        Campus Customs makes Yale apparel for students, alumni and families: residential college crests,
        graduate and professional schools, varsity sports, and gifts for every Yale relative.
      </p>
      <h2>Shop with help</h2>
      <p>
        Our shop assistant can answer questions about any item. It checks the live catalogue, so the prices
        and sizes it tells you are the ones on our shelves, and it shows you matching items as you chat.
      </p>
      <h2>Your account</h2>
      <p>
        Create an account to keep your conversation with the shop assistant, so you can pick up where you left off.
      </p>
      <p>
        <Link to="/products" className="button button-primary">Browse products</Link>
      </p>
    </div>
  )
}
