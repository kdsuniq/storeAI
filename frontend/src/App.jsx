import { Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'

const API = import.meta.env.VITE_API_URL || '/api'

const getToken = () => localStorage.getItem('token') || ''

const parseSpecs = (text) => {
  if (!text.trim()) return {}
  return text.split('\n').reduce((acc, line) => {
    const [k, ...rest] = line.split(':')
    if (!k || !rest.length) return acc
    acc[k.trim()] = rest.join(':').trim()
    return acc
  }, {})
}

const extractError = (data) => {
  if (!data) return 'Неизвестная ошибка'
  if (data.error) return data.error
  const firstKey = Object.keys(data)[0]
  if (!firstKey) return 'Ошибка запроса'
  const val = data[firstKey]
  return Array.isArray(val) ? val[0] : String(val)
}

function Header({ token, onLogout }) {
  return (
    <header className="header-wrap">
      <div className="topline">
        <div className="brand">Store with AI</div>
        <div className="actions">
          {token ? <Link className="btn btn-light" to="/account">Разместить товар</Link> : <Link className="btn btn-light" to="/auth">Стать продавцом</Link>}
          <Link className="btn btn-accent" to="/cart">Корзина</Link>
          {token ? <button className="btn btn-outline" onClick={onLogout}>Выйти</button> : <Link className="btn btn-outline" to="/auth">Вход</Link>}
        </div>
      </div>
      <nav className="menu">
        <Link to="/">Все товары</Link>
        <Link to="/account">Кабинет продавца</Link>
      </nav>
    </header>
  )
}

function ProductsPage({ token }) {
  const [products, setProducts] = useState([])
  const [query, setQuery] = useState('')
  const [aiQuestion, setAiQuestion] = useState('')
  const [aiAnswer, setAiAnswer] = useState('')
  const [error, setError] = useState('')

  const load = async () => {
    const res = await fetch(`${API}/products/`)
    const data = await res.json().catch(() => [])
    setProducts(Array.isArray(data) ? data : [])
  }

  useEffect(() => { load() }, [])

  const filtered = useMemo(() => {
    if (!query.trim()) return products
    const q = query.toLowerCase()
    return products.filter((p) => `${p.name} ${p.description}`.toLowerCase().includes(q))
  }, [products, query])

  const addToCart = async (productId) => {
    setError('')
    if (!token) return setError('Чтобы добавить в корзину, нужно войти в аккаунт.')
    const res = await fetch(`${API}/products/cart/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Token ${token}` },
      body: JSON.stringify({ product_id: productId, quantity: 1 })
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      return setError(extractError(data))
    }
    setError('Товар добавлен в корзину.')
  }

  const askAI = async () => {
    const res = await fetch(`${API}/ai/chat/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: aiQuestion })
    })
    const data = await res.json()
    setAiAnswer(data.answer || data.error || 'Ответ не получен')
  }

  return (
    <>
      <section className="hero-market">
        <h1>Маркетплейс товаров с AI</h1>
        <p>Покупатели смотрят все товары, продавцы публикуют через личный кабинет.</p>
      </section>

      <div className="layout">
        <section className="panel">
          <div className="panel-head">
            <h2>Каталог</h2>
            <input placeholder="Поиск по товарам" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          {error && <p className="note">{error}</p>}
          <div className="catalog-grid">
            {filtered.map((p) => (
              <article className="product-card" key={p.id}>
                <div className="mock-photo" />
                <h3>{p.name}</h3>
                <p className="price">{p.price} ₽</p>
                <p className="meta">{p.category?.name || 'Без категории'} · продавец: {p.owner_username || 'пользователь'}</p>
                <p className="desc">{p.description}</p>
                <button className="btn btn-accent" onClick={() => addToCart(p.id)}>В корзину</button>
              </article>
            ))}
          </div>
        </section>

        <aside className="panel ai-panel">
          <h2>AI помощник</h2>
          <textarea rows={5} value={aiQuestion} onChange={(e) => setAiQuestion(e.target.value)} placeholder="Например: помоги выбрать товар для офиса до 50 000 ₽" />
          <button className="btn btn-light" onClick={askAI}>Спросить</button>
          <p>{aiAnswer}</p>
        </aside>
      </div>
    </>
  )
}

function AuthPage({ onAuth }) {
  const [mode, setMode] = useState('login')
  const [error, setError] = useState('')
  const [form, setForm] = useState({ username: '', email: '', password: '' })
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    const url = mode === 'login' ? `${API}/auth/login/` : `${API}/auth/register/`
    const payload = mode === 'login' ? { username: form.username, password: form.password } : form
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) return setError(extractError(data))

    localStorage.setItem('token', data.token)
    onAuth(data.token)
    navigate('/account')
  }

  return (
    <section className="auth-wrap">
      <div className="panel auth-panel">
        <h2>{mode === 'login' ? 'Вход' : 'Регистрация продавца'}</h2>
        <form onSubmit={submit}>
          <input placeholder="Логин" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
          {mode === 'register' && <input placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />}
          <input type="password" placeholder="Пароль (мин. 6 символов)" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
          {error && <p className="note">{error}</p>}
          <button className="btn btn-accent" type="submit">{mode === 'login' ? 'Войти' : 'Создать аккаунт'}</button>
        </form>
        <button className="btn btn-outline" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
          {mode === 'login' ? 'Нет аккаунта? Регистрация' : 'Уже есть аккаунт? Войти'}
        </button>
      </div>
    </section>
  )
}

function AccountPage({ token }) {
  const [categories, setCategories] = useState([])
  const [myProducts, setMyProducts] = useState([])
  const [cat, setCat] = useState({ name: '', description: '' })
  const [form, setForm] = useState({ name: '', description: '', price: '', category_id: '', specsText: '' })
  const [msg, setMsg] = useState('')

  const load = async () => {
    const [cRes, pRes] = await Promise.all([
      fetch(`${API}/categories/`),
      fetch(`${API}/products/my-products/`, { headers: { Authorization: `Token ${token}` } })
    ])
    if (pRes.status === 401) {
      setMsg('Сессия истекла. Войдите заново.')
      return
    }
    const cData = await cRes.json().catch(() => [])
    const pData = await pRes.json().catch(() => [])
    setCategories(Array.isArray(cData) ? cData : [])
    setMyProducts(Array.isArray(pData) ? pData : [])
  }

  useEffect(() => { load() }, [token])

  const addCategory = async (e) => {
    e.preventDefault()
    const res = await fetch(`${API}/categories/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Token ${token}` },
      body: JSON.stringify(cat)
    })
    if (!res.ok) return setMsg('Не удалось создать категорию')
    setMsg('Категория создана')
    setCat({ name: '', description: '' })
    load()
  }

  const generateDescription = async () => {
    if (!form.name.trim()) return setMsg('Введите название товара перед генерацией')
    const selected = categories.find((c) => c.id === form.category_id)
    const res = await fetch(`${API}/ai/generate-description/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: form.name, category: selected?.name || '', specs: parseSpecs(form.specsText) })
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) return setMsg(extractError(data))
    setForm((p) => ({ ...p, description: data.description || p.description }))
    setMsg('Описание сгенерировано')
  }

  const addProduct = async (e) => {
    e.preventDefault()
    const res = await fetch(`${API}/products/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Token ${token}` },
      body: JSON.stringify({
        name: form.name,
        description: form.description,
        price: Number(form.price),
        category_id: form.category_id,
        specs: parseSpecs(form.specsText)
      })
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) return setMsg(extractError(data))
    setMsg('Товар опубликован')
    setForm({ name: '', description: '', price: '', category_id: '', specsText: '' })
    load()
  }

  return (
    <div className="layout">
      <section className="panel">
        <h2>Кабинет продавца</h2>
        {msg && <p className="note">{msg}</p>}
        <form onSubmit={addCategory} className="form-block">
          <h3>1) Создать категорию</h3>
          <input required placeholder="Название категории" value={cat.name} onChange={(e) => setCat({ ...cat, name: e.target.value })} />
          <textarea rows={3} placeholder="Описание категории" value={cat.description} onChange={(e) => setCat({ ...cat, description: e.target.value })} />
          <button className="btn btn-light" type="submit">Сохранить категорию</button>
        </form>

        <form onSubmit={addProduct} className="form-block">
          <h3>2) Разместить товар</h3>
          <input required placeholder="Название товара" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input required type="number" min="0" step="0.01" placeholder="Цена" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />
          <select required value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
            <option value="">Выберите категорию</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <textarea rows={4} placeholder={'Характеристики\nЦвет: Черный\nПамять: 256 ГБ'} value={form.specsText} onChange={(e) => setForm({ ...form, specsText: e.target.value })} />
          <textarea required rows={6} placeholder="Описание" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <div className="actions-row">
            <button className="btn btn-outline" type="button" onClick={generateDescription}>Сгенерировать описание AI</button>
            <button className="btn btn-accent" type="submit">Опубликовать товар</button>
          </div>
        </form>
      </section>

      <section className="panel">
        <h2>Мои товары</h2>
        <div className="catalog-grid">
          {myProducts.map((p) => (
            <article className="product-card" key={p.id}>
              <div className="mock-photo" />
              <h3>{p.name}</h3>
              <p className="price">{p.price} ₽</p>
              <p className="meta">{p.category?.name}</p>
              <p className="desc">{p.description}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}

function CartPage({ token }) {
  const [cart, setCart] = useState({ items: [], total: 0 })

  const load = async () => {
    const res = await fetch(`${API}/products/cart/`, { headers: { Authorization: `Token ${token}` } })
    if (!res.ok) return
    const data = await res.json().catch(() => ({ items: [], total: 0 }))
    setCart({
      items: Array.isArray(data.items) ? data.items : [],
      total: Number(data.total || 0),
    })
  }

  useEffect(() => { if (token) load() }, [token])

  const removeItem = async (id) => {
    await fetch(`${API}/products/cart/${id}/`, { method: 'DELETE', headers: { Authorization: `Token ${token}` } })
    load()
  }

  if (!token) return <section className="panel"><p>Войдите в аккаунт, чтобы пользоваться корзиной.</p></section>

  return (
    <section className="panel">
      <h2>Корзина</h2>
      {cart.items.map((item) => (
        <article className="product-row" key={item.id}>
          <div>
            <h3>{item.product.name}</h3>
            <p className="meta">{item.quantity} шт · {item.product.price} ₽</p>
          </div>
          <button className="btn btn-outline" onClick={() => removeItem(item.id)}>Удалить</button>
        </article>
      ))}
      <h3>Итого: {Number(cart.total).toFixed(2)} ₽</h3>
    </section>
  )
}

export default function App() {
  const [token, setToken] = useState(getToken())

  useEffect(() => {
    const check = async () => {
      if (!token) return
      const res = await fetch(`${API}/auth/me/`, { headers: { Authorization: `Token ${token}` } })
      if (!res.ok) {
        localStorage.removeItem('token')
        setToken('')
      }
    }
    check()
  }, [token])

  const onLogout = () => {
    localStorage.removeItem('token')
    setToken('')
  }

  return (
    <div className="page">
      <Header token={token} onLogout={onLogout} />
      <Routes>
        <Route path="/" element={<ProductsPage token={token} />} />
        <Route path="/auth" element={<AuthPage onAuth={setToken} />} />
        <Route path="/cart" element={<CartPage token={token} />} />
        <Route path="/account" element={token ? <AccountPage token={token} /> : <Navigate to="/auth" replace />} />
      </Routes>
    </div>
  )
}
