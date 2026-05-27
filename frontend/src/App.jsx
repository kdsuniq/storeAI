import { Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'

const API = 'http://127.0.0.1:8000/api'

const getAuth = () => ({
  access: localStorage.getItem('access_token') || '',
  refresh: localStorage.getItem('refresh_token') || '',
})

const saveAuth = (tokens) => {
  localStorage.setItem('access_token', tokens?.access || '')
  localStorage.setItem('refresh_token', tokens?.refresh || '')
}

const clearAuth = () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

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

async function apiFetch(path, { method = 'GET', body, auth, setAuth } = {}) {
  const headers = {}
  if (body) headers['Content-Type'] = 'application/json'
  if (auth?.access) headers.Authorization = `Bearer ${auth.access}`

  let res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401 && auth?.refresh && setAuth) {
    const refreshRes = await fetch(`${API}/auth/token/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: auth.refresh }),
    })
    const refreshData = await refreshRes.json().catch(() => ({}))
    if (refreshRes.ok && refreshData.access) {
      const nextAuth = { access: refreshData.access, refresh: refreshData.refresh || auth.refresh }
      setAuth(nextAuth)
      saveAuth(nextAuth)
      const retryHeaders = { ...headers, Authorization: `Bearer ${nextAuth.access}` }
      res = await fetch(`${API}${path}`, {
        method,
        headers: retryHeaders,
        body: body ? JSON.stringify(body) : undefined,
      })
    } else {
      clearAuth()
      setAuth({ access: '', refresh: '' })
    }
  }

  const data = await res.json().catch(() => ({}))
  return { ok: res.ok, status: res.status, data }
}

function Header({ isAuth, onLogout }) {
  return (
    <header className="header-wrap">
      <div className="topline">
        <div className="brand">Store with AI</div>
        <div className="actions">
          {isAuth ? <Link className="btn btn-light" to="/account">Разместить товар</Link> : <Link className="btn btn-light" to="/auth">Стать продавцом</Link>}
          <Link className="btn btn-accent" to="/cart">Корзина</Link>
          {isAuth ? <button className="btn btn-outline" onClick={onLogout}>Выйти</button> : <Link className="btn btn-outline" to="/auth">Вход</Link>}
        </div>
      </div>
      <nav className="menu">
        <Link to="/">Все товары</Link>
        <Link to="/account">Кабинет продавца</Link>
      </nav>
    </header>
  )
}

function ProductsPage({ auth, setAuth }) {
  const [products, setProducts] = useState([])
  const [query, setQuery] = useState('')
  const [aiQuestion, setAiQuestion] = useState('')
  const [aiAnswer, setAiAnswer] = useState('')
  const [error, setError] = useState('')

  const load = async () => {
    const { data } = await apiFetch('/products/')
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
    if (!auth.access) return setError('Чтобы добавить в корзину, нужно войти в аккаунт.')
    const res = await apiFetch('/products/cart/', {
      method: 'POST',
      body: { product_id: productId, quantity: 1 },
      auth,
      setAuth,
    })
    if (!res.ok) return setError(extractError(res.data))
    setError('Товар добавлен в корзину.')
  }

  const askAI = async () => {
    const res = await apiFetch('/ai/chat/', { method: 'POST', body: { message: aiQuestion } })
    setAiAnswer(res.data.answer || res.data.error || 'Ответ не получен')
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

function AuthPage({ setAuth }) {
  const [mode, setMode] = useState('login')
  const [error, setError] = useState('')
  const [form, setForm] = useState({ username: '', email: '', password: '' })
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    const path = mode === 'login' ? '/auth/login/' : '/auth/register/'
    const payload = mode === 'login' ? { username: form.username, password: form.password } : form
    const res = await apiFetch(path, { method: 'POST', body: payload })
    if (!res.ok) return setError(extractError(res.data))

    const tokens = res.data.tokens || {}
    if (!tokens.access || !tokens.refresh) return setError('Сервер не вернул JWT токены')

    saveAuth(tokens)
    setAuth(tokens)
    navigate('/account')
  }

  return (
    <section className="auth-wrap">
      <div className="panel auth-panel">
        <div className="auth-tabs">
          <button type="button" className={`auth-tab ${mode === 'login' ? 'active' : ''}`} onClick={() => setMode('login')}>Вход</button>
          <button type="button" className={`auth-tab ${mode === 'register' ? 'active' : ''}`} onClick={() => setMode('register')}>Регистрация</button>
        </div>
        <h2>{mode === 'login' ? 'Вход' : 'Регистрация продавца'}</h2>
        <form onSubmit={submit}>
          <input placeholder="Логин" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
          {mode === 'register' && <input placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />}
          <input type="password" placeholder="Пароль (мин. 6 символов)" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
          {error && <p className="note">{error}</p>}
          <button className="btn btn-accent" type="submit">{mode === 'login' ? 'Войти' : 'Создать аккаунт'}</button>
        </form>
      </div>
    </section>
  )
}

function AccountPage({ auth, setAuth }) {
  const [profile, setProfile] = useState(null)
  const [categories, setCategories] = useState([])
  const [myProducts, setMyProducts] = useState([])
  const [orders, setOrders] = useState([])
  const [cat, setCat] = useState({ name: '', description: '' })
  const [form, setForm] = useState({ name: '', description: '', price: '', category_id: '', specsText: '' })
  const [insights, setInsights] = useState('')
  const [stats, setStats] = useState(null)
  const [msg, setMsg] = useState('')

  const load = async () => {
    const [me, c, p, o] = await Promise.all([
      apiFetch('/auth/me/', { auth, setAuth }),
      apiFetch('/categories/'),
      apiFetch('/products/my-products/', { auth, setAuth }),
      apiFetch('/products/my-orders/', { auth, setAuth }),
    ])

    if (!me.ok || !p.ok) {
      setMsg('Сессия истекла. Войдите заново.')
      return
    }

    setProfile(me.data || null)
    setCategories(Array.isArray(c.data) ? c.data : [])
    setMyProducts(Array.isArray(p.data) ? p.data : [])
    setOrders(Array.isArray(o.data) ? o.data : [])
  }

  useEffect(() => { load() }, [auth.access])

  const addCategory = async (e) => {
    e.preventDefault()
    const res = await apiFetch('/categories/', { method: 'POST', body: cat, auth, setAuth })
    if (!res.ok) return setMsg(extractError(res.data))
    setMsg('Категория создана')
    setCat({ name: '', description: '' })
    load()
  }

  const generateDescription = async () => {
    if (!form.name.trim()) return setMsg('Введите название товара перед генерацией')
    const selected = categories.find((c) => c.id === form.category_id)
    const res = await apiFetch('/ai/generate-description/', {
      method: 'POST',
      body: { name: form.name, category: selected?.name || '', specs: parseSpecs(form.specsText) },
    })
    if (!res.ok) return setMsg(extractError(res.data))
    setForm((p) => ({ ...p, description: res.data.description || p.description }))
    setMsg('Описание сгенерировано')
  }

  const addProduct = async (e) => {
    e.preventDefault()
    const res = await apiFetch('/products/', {
      method: 'POST',
      body: {
        name: form.name,
        description: form.description,
        price: Number(form.price),
        category_id: form.category_id,
        specs: parseSpecs(form.specsText),
      },
      auth,
      setAuth,
    })
    if (!res.ok) return setMsg(extractError(res.data))
    setMsg('Товар опубликован')
    setForm({ name: '', description: '', price: '', category_id: '', specsText: '' })
    load()
  }

  const loadInsights = async () => {
    const res = await apiFetch('/ai/market-insights/', { auth, setAuth })
    if (!res.ok) return setMsg(extractError(res.data))
    setInsights(res.data.insights || '')
    setStats(res.data.stats || null)
  }

  const updateOrderStatus = async (orderId, statusValue) => {
    const res = await apiFetch(`/products/orders/${orderId}/status/`, {
      method: 'PATCH',
      body: { status: statusValue },
      auth,
      setAuth,
    })
    if (!res.ok) return setMsg(extractError(res.data))
    setMsg('Статус заказа обновлен')
    load()
  }

  return (
    <div className="layout">
      <section className="panel">
        <h2>Кабинет продавца</h2>
        {profile && <p className="meta">Пользователь: {profile.username} {profile.email ? `· ${profile.email}` : ''}</p>}
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

        <h2 style={{ marginTop: 16 }}>Мои заказы</h2>
        {orders.map((o) => (
          <article className="product-card" key={o.id}>
            <p><b>Заказ #{o.id}</b> · {o.total} ₽ · статус: {o.status}</p>
            <p className="meta">{o.full_name}, {o.phone}, {o.city}, {o.address}</p>
            <div className="actions-row">
              <select defaultValue={o.status} onChange={(e) => updateOrderStatus(o.id, e.target.value)}>
                <option value="new">new</option>
                <option value="paid">paid</option>
                <option value="shipped">shipped</option>
                <option value="done">done</option>
                <option value="canceled">canceled</option>
              </select>
            </div>
          </article>
        ))}
      </section>

      <section className="panel">
        <h2>AI анализатор спроса</h2>
        <button className="btn btn-light" onClick={loadInsights}>Показать статистику и рекомендации</button>
        {stats && (
          <div>
            <p className="meta">Товаров у продавца: {stats.seller_products_count}</p>
            <p className="meta">Добавлений в корзину: {stats.total_cart_additions}</p>
          </div>
        )}
        {insights && <p>{insights}</p>}
      </section>
    </div>
  )
}

function CartPage({ auth, setAuth }) {
  const [cart, setCart] = useState({ items: [], total: 0 })
  const [msg, setMsg] = useState('')
  const [checkoutData, setCheckoutData] = useState({ full_name: '', phone: '', city: '', address: '', comment: '' })

  const load = async () => {
    const res = await apiFetch('/products/cart/', { auth, setAuth })
    if (!res.ok) return
    setCart({
      items: Array.isArray(res.data.items) ? res.data.items : [],
      total: Number(res.data.total || 0),
    })
  }

  useEffect(() => { if (auth.access) load() }, [auth.access])

  const removeItem = async (id) => {
    await apiFetch(`/products/cart/${id}/`, { method: 'DELETE', auth, setAuth })
    load()
  }

  const checkout = async () => {
    setMsg('')
    const res = await apiFetch('/products/cart/checkout/', { method: 'POST', body: checkoutData, auth, setAuth })
    if (!res.ok) return setMsg(extractError(res.data))
    setMsg(`Заказ оформлен на сумму ${Number(res.data.order?.total || 0).toFixed(2)} ₽`)
    load()
  }

  if (!auth.access) return <section className="panel"><p>Войдите в аккаунт, чтобы пользоваться корзиной.</p></section>

  return (
    <section className="panel">
      <h2>Корзина</h2>
      {msg && <p className="note">{msg}</p>}
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
      <div className="form-block">
        <h3>Данные для доставки</h3>
        <input placeholder="ФИО" value={checkoutData.full_name} onChange={(e) => setCheckoutData({ ...checkoutData, full_name: e.target.value })} />
        <input placeholder="Телефон" value={checkoutData.phone} onChange={(e) => setCheckoutData({ ...checkoutData, phone: e.target.value })} />
        <input placeholder="Город" value={checkoutData.city} onChange={(e) => setCheckoutData({ ...checkoutData, city: e.target.value })} />
        <input placeholder="Адрес" value={checkoutData.address} onChange={(e) => setCheckoutData({ ...checkoutData, address: e.target.value })} />
        <textarea rows={3} placeholder="Комментарий к заказу" value={checkoutData.comment} onChange={(e) => setCheckoutData({ ...checkoutData, comment: e.target.value })} />
      </div>
      <button className="btn btn-accent" onClick={checkout} disabled={!cart.items.length}>Оформить заказ</button>
    </section>
  )
}

export default function App() {
  const [auth, setAuth] = useState(getAuth())

  useEffect(() => {
    const check = async () => {
      if (!auth.access) return
      const res = await apiFetch('/auth/me/', { auth, setAuth })
      if (!res.ok) {
        clearAuth()
        setAuth({ access: '', refresh: '' })
      }
    }
    check()
  }, [auth.access])

  const onLogout = () => {
    clearAuth()
    setAuth({ access: '', refresh: '' })
  }

  const isAuth = Boolean(auth.access)

  return (
    <div className="page">
      <Header isAuth={isAuth} onLogout={onLogout} />
      <Routes>
        <Route path="/" element={<ProductsPage auth={auth} setAuth={setAuth} />} />
        <Route path="/auth" element={<AuthPage setAuth={setAuth} />} />
        <Route path="/cart" element={<CartPage auth={auth} setAuth={setAuth} />} />
        <Route path="/account" element={isAuth ? <AccountPage auth={auth} setAuth={setAuth} /> : <Navigate to="/auth" replace />} />
      </Routes>
    </div>
  )
}
