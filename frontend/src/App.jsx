import { Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'

const API = import.meta.env.VITE_API_URL || '/api'

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

const getList = (data) => {
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.results)) return data.results
  return []
}

const getPageMeta = (data, fallbackLength = 0) => ({
  count: Number(data?.count ?? fallbackLength),
  next: data?.next || null,
  previous: data?.previous || null,
})

const validateAuthForm = (mode, form) => {
  if (form.username.trim().length < 3) return 'Логин должен быть не короче 3 символов'
  if (form.password.length < 8) return 'Пароль должен быть не короче 8 символов'
  if (mode === 'register' && form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    return 'Введите корректный email'
  }
  return ''
}

const validateCheckoutForm = (data) => {
  if (data.full_name.trim().split(/\s+/).length < 2) return 'Укажите имя и фамилию'
  if (!/^[0-9+()\-\s]{7,20}$/.test(data.phone.trim())) return 'Введите корректный телефон'
  if (data.city.trim().length < 2) return 'Укажите город'
  if (data.address.trim().length < 10) return 'Адрес должен быть не короче 10 символов'
  return ''
}

async function apiFetch(path, { method = 'GET', body, auth, setAuth } = {}) {
  const headers = {}
  if (body) headers['Content-Type'] = 'application/json'
  if (auth?.access) headers.Authorization = `Bearer ${auth.access}`

  let res
  try {
    res = await fetch(`${API}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch (err) {
    return { ok: false, status: 0, data: { error: 'Не удалось подключиться к серверу' } }
  }

  if (res.status === 401 && auth?.refresh && setAuth) {
    let refreshRes
    try {
      refreshRes = await fetch(`${API}/auth/token/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: auth.refresh }),
      })
    } catch (err) {
      clearAuth()
      setAuth({ access: '', refresh: '' })
      return { ok: false, status: 0, data: { error: 'Не удалось обновить сессию' } }
    }
    const refreshData = await refreshRes.json().catch(() => ({}))
    if (refreshRes.ok && refreshData.access) {
      const nextAuth = { access: refreshData.access, refresh: refreshData.refresh || auth.refresh }
      setAuth(nextAuth)
      saveAuth(nextAuth)
      const retryHeaders = { ...headers, Authorization: `Bearer ${nextAuth.access}` }
      try {
        res = await fetch(`${API}${path}`, {
          method,
          headers: retryHeaders,
          body: body ? JSON.stringify(body) : undefined,
        })
      } catch (err) {
        return { ok: false, status: 0, data: { error: 'Не удалось подключиться к серверу' } }
      }
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
  const [categories, setCategories] = useState([])
  const [cartItems, setCartItems] = useState({})
  const [filters, setFilters] = useState({
    search: '',
    category: '',
    min_price: '',
    max_price: '',
    ordering: '-created_at',
  })
  const [page, setPage] = useState(1)
  const [pageMeta, setPageMeta] = useState({ count: 0, next: null, previous: null })
  const [aiQuestion, setAiQuestion] = useState('')
  const [aiAnswer, setAiAnswer] = useState('')
  const [aiChatRecommendations, setAiChatRecommendations] = useState([])
  const [aiChatQuestions, setAiChatQuestions] = useState([])
  const [aiChatInteractionId, setAiChatInteractionId] = useState(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [error, setError] = useState('')
  const [cartTotalCount, setCartTotalCount] = useState(0)
  const [productsLoading, setProductsLoading] = useState(false)

  const loadProducts = async (pageNumber = page) => {
    setProductsLoading(true)
    const params = new URLSearchParams({ page: String(pageNumber), page_size: '8' })
    Object.entries(filters).forEach(([key, value]) => {
      if (String(value).trim()) params.set(key, String(value).trim())
    })
    const { data } = await apiFetch(`/products/?${params.toString()}`)
    const list = getList(data)
    setProducts(list)
    setPageMeta(getPageMeta(data, list.length))
    setProductsLoading(false)
  }

  const loadCategories = async () => {
    const { data } = await apiFetch('/categories/')
    setCategories(getList(data))
  }

  const loadCart = async () => {
    if (!auth.access) return
    const res = await apiFetch('/products/cart/', { auth, setAuth })
    if (!res.ok) return
    
    const items = Array.isArray(res.data.items) ? res.data.items : []
    const cartMap = {}
    let totalCount = 0
    items.forEach(item => {
      cartMap[item.product.id] = {
        quantity: item.quantity,
        cartItemId: item.id
      }
      totalCount += item.quantity
    })
    setCartItems(cartMap)
    setCartTotalCount(totalCount)
  }

  useEffect(() => {
    loadCategories()
    loadCart()
  }, [])

  useEffect(() => {
    loadProducts(page)
  }, [page, filters.search, filters.category, filters.min_price, filters.max_price, filters.ordering])

  useEffect(() => {
    loadCart()
  }, [auth.access])

  const totalPages = Math.max(1, Math.ceil(pageMeta.count / 8))

  const updateFilter = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
    setPage(1)
  }

  const updateCartQuantity = async (productId, newQuantity) => {
    if (!auth.access) {
      setError('Чтобы добавить в корзину, нужно войти в аккаунт.')
      return
    }

    const product = products.find(p => p.id === productId)
    if (!product) return

    if (newQuantity < 0) newQuantity = 0
    
    if (newQuantity === 0) {
      const cartItemId = cartItems[productId]?.cartItemId
      if (cartItemId) {
        const res = await apiFetch(`/products/cart/${cartItemId}/`, { 
          method: 'DELETE', 
          auth, 
          setAuth 
        })
        if (!res.ok) {
          setError(extractError(res.data))
          return
        }
        await loadCart()
      }
      return
    }

    if (newQuantity > product.stock) {
      setError(`Недостаточно товара. В наличии: ${product.stock} шт.`)
      return
    }

    const res = await apiFetch('/products/cart/update/', {
      method: 'PATCH',
      body: { product_id: productId, quantity: newQuantity },
      auth,
      setAuth,
    })

    if (!res.ok) {
      setError(extractError(res.data))
      return
    }

    await apiFetch('/ai/track-view/', {
      method: 'POST',
      body: { product_id: productId, source: 'catalog', query: filters.search },
      auth,
      setAuth,
    })
    await loadCart()
    setError('')
  }

  const getQuantityInCart = (productId) => {
    return cartItems[productId]?.quantity || 0
  }

  const askAI = async () => {
    if (!aiQuestion.trim()) return
    
    setAiLoading(true)
    setAiAnswer('')
    
    try {
      const res = await apiFetch('/ai/chat/', { 
        method: 'POST', 
        body: { message: aiQuestion, format: 'structured' },
        auth,
        setAuth,
      })
      
      if (res.ok) {
        setAiAnswer(res.data.answer || 'Ответ не получен')
        setAiChatRecommendations(res.data.recommendations || [])
        setAiChatQuestions(res.data.clarifying_questions || [])
        setAiChatInteractionId(res.data.interaction_id || null)
      } else {
        setAiAnswer('❌ Ошибка: ' + (res.data.error || 'Не удалось получить ответ'))
        setAiChatRecommendations([])
        setAiChatQuestions([])
        setAiChatInteractionId(null)
      }
    } catch (err) {
      setAiAnswer('❌ Ошибка соединения. Попробуйте позже.')
    } finally {
      setAiLoading(false)
    }
  }

  const addProductFromAI = async (productId, queryText = aiQuestion) => {
    if (!auth.access) {
      setError('Войдите в аккаунт, чтобы добавить товар в корзину')
      return
    }
    const res = await apiFetch('/products/cart/', {
      method: 'POST',
      body: { product_id: productId, quantity: 1 },
      auth,
      setAuth,
    })
    if (res.ok) {
      await apiFetch('/ai/track-view/', {
        method: 'POST',
        body: { product_id: productId, source: 'ai', query: queryText },
        auth,
        setAuth,
      })
      setError('Товар добавлен в корзину')
      loadCart()
    } else {
      setError(extractError(res.data))
    }
  }

  const sendAIFeedback = async (interactionId, helpful, feedbackText = '') => {
    if (!interactionId) return
    const res = await apiFetch('/ai/feedback/', {
      method: 'POST',
      body: { interaction_id: interactionId, helpful, feedback_text: feedbackText },
      auth,
      setAuth,
    })
    setError(res.ok ? 'Спасибо, оценка AI сохранена' : extractError(res.data))
  }

  const getStockClass = (status) => {
    switch(status) {
      case 'in_stock': return 'in-stock'
      case 'low_stock': return 'low-stock'
      default: return 'out-of-stock'
    }
  }

  return (
    <>
      <section className="hero-market">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1>Маркетплейс товаров с AI</h1>
            <p>Покупатели смотрят все товары, продавцы публикуют через личный кабинет.</p>
          </div>
          {auth.access && (
            <Link to="/cart" className="cart-icon-link">
              <div className="cart-icon">
                🛒
                {cartTotalCount > 0 && (
                  <span className="cart-badge">{cartTotalCount}</span>
                )}
              </div>
            </Link>
          )}
        </div>
      </section>

      <div className="layout">
        <section className="panel">
          <div className="panel-head">
            <h2>Каталог</h2>
          </div>
          <div className="filters-grid">
            <input placeholder="Поиск по товарам" value={filters.search} onChange={(e) => updateFilter('search', e.target.value)} />
            <select value={filters.category} onChange={(e) => updateFilter('category', e.target.value)}>
              <option value="">Все категории</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <input type="number" min="0" step="0.01" placeholder="Цена от" value={filters.min_price} onChange={(e) => updateFilter('min_price', e.target.value)} />
            <input type="number" min="0" step="0.01" placeholder="Цена до" value={filters.max_price} onChange={(e) => updateFilter('max_price', e.target.value)} />
            <select value={filters.ordering} onChange={(e) => updateFilter('ordering', e.target.value)}>
              <option value="-created_at">Сначала новые</option>
              <option value="price">Сначала дешевле</option>
              <option value="-price">Сначала дороже</option>
              <option value="name">По названию</option>
            </select>
          </div>
          {error && <p className="note">{error}</p>}
          {productsLoading && <p className="meta">Загружаем товары...</p>}
          <div className="catalog-grid">
            {products.map((p) => {
              const cartQuantity = getQuantityInCart(p.id)
              const isInStock = p.is_in_stock || p.stock > 0
              
              return (
                <article className="product-card" key={p.id}>
                  <div className="mock-photo" />
                  <h3>{p.name}</h3>
                  <p className="price">{p.price} ₽</p>
                  
                  <div className={`stock-badge ${getStockClass(p.stock_status)}`}>
                    {p.in_stock_display || (p.stock > 0 ? `В наличии (${p.stock} шт.)` : 'Нет в наличии')}
                  </div>
                  
                  <p className="meta">{p.category?.name || 'Без категории'} · продавец: {p.owner_username || 'пользователь'}</p>
                  <p className="desc">{p.description}</p>
                  
                  {isInStock ? (
                    <div className="cart-controls">
                      {cartQuantity > 0 ? (
                        <div className="quantity-controls">
                          <button 
                            className="qty-btn"
                            onClick={() => updateCartQuantity(p.id, cartQuantity - 1)}
                          >
                            -
                          </button>
                          <span className="qty-value">{cartQuantity}</span>
                          <button 
                            className="qty-btn"
                            onClick={() => updateCartQuantity(p.id, cartQuantity + 1)}
                            disabled={cartQuantity >= p.stock}
                          >
                            +
                          </button>
                        </div>
                      ) : (
                        <button 
                          className="btn btn-accent add-to-cart-btn"
                          onClick={() => updateCartQuantity(p.id, 1)}
                        >
                          В корзину
                        </button>
                      )}
                    </div>
                  ) : (
                    <button className="btn btn-disabled" disabled>
                      Нет в наличии
                    </button>
                  )}
                </article>
              )
            })}
          </div>
          {!productsLoading && products.length === 0 && <p className="meta">По выбранным фильтрам товаров нет.</p>}
          <div className="pagination-row">
            <button className="btn btn-dark-outline" type="button" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={!pageMeta.previous}>
              Назад
            </button>
            <span>Страница {page} из {totalPages}</span>
            <button className="btn btn-dark-outline" type="button" onClick={() => setPage((value) => value + 1)} disabled={!pageMeta.next}>
              Вперёд
            </button>
          </div>
        </section>

        <aside className="panel ai-panel">
  {/* Существующий AI помощник */}
  <h2>💬 AI помощник</h2>
  <textarea 
    rows={5} 
    value={aiQuestion} 
    onChange={(e) => setAiQuestion(e.target.value)} 
    placeholder="Например: помоги выбрать товар для офиса до 50 000 ₽"
    disabled={aiLoading}
  />
  <button 
    className="btn btn-light" 
    onClick={askAI}
    disabled={aiLoading || !aiQuestion.trim()}
  >
    {aiLoading ? '⏳ Думаю...' : '💬 Спросить'}
  </button>
  
  {aiLoading && (
    <div className="ai-loading">
      <div className="loading-spinner"></div>
      <p>AI анализирует ваш запрос...</p>
    </div>
  )}
  
  {aiAnswer && !aiLoading && (
    <div className="ai-answer">
      <div className="ai-answer-header">🤖 Ответ AI:</div>
      <div className="ai-answer-content">
        {aiAnswer.split('\n').map((line, i) => (
          <p key={i} className={line.startsWith('•') || line.startsWith('-') ? 'list-item' : ''}>
            {line}
          </p>
        ))}
      </div>
      {aiChatQuestions.length > 0 && (
        <div className="ai-followups">
          <b>Уточняющие вопросы:</b>
          {aiChatQuestions.map((question) => (
            <button key={question} className="chip-button" type="button" onClick={() => setAiQuestion(question)}>
              {question}
            </button>
          ))}
        </div>
      )}
      {aiChatRecommendations.length > 0 && (
        <div className="recommendations-list compact">
          {aiChatRecommendations.map((rec) => (
            <div className="recommendation-card" key={rec.product_id}>
              <div className="card-content">
                <div className="card-header">
                  <h4>{rec.name}</h4>
                  <span className="price-badge medium">{rec.price} ₽</span>
                </div>
                <div className="reason">{rec.why_fits}</div>
                <button className="btn-small" type="button" onClick={() => addProductFromAI(rec.product_id)}>
                  В корзину
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      {aiChatInteractionId && (
        <div className="ai-feedback-row">
          <button className="btn btn-dark-outline" type="button" onClick={() => sendAIFeedback(aiChatInteractionId, true)}>Помогло</button>
          <button className="btn btn-dark-outline" type="button" onClick={() => sendAIFeedback(aiChatInteractionId, false, aiQuestion)}>Не помогло</button>
        </div>
      )}
    </div>
  )}
  
  <AIPriceSearchWidget 
    auth={auth}
    setAuth={setAuth}
    onAddToCart={addProductFromAI}
    onFeedback={sendAIFeedback}
  />
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
    const validationError = validateAuthForm(mode, form)
    if (validationError) return setError(validationError)
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
          {mode === 'register' && <input type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />}
          <input type="password" minLength={8} placeholder="Пароль (мин. 8 символов)" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
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
  const [form, setForm] = useState({ 
    name: '', 
    description: '', 
    price: '', 
    category_id: '', 
    specsText: '',
    stock: '',
    low_stock_threshold: ''
  })
  const [insights, setInsights] = useState('')
  const [stats, setStats] = useState(null)
  const [msg, setMsg] = useState('')
  
  const [editingProduct, setEditingProduct] = useState(null)
  const [editingStockValue, setEditingStockValue] = useState('')
  const [editingPriceValue, setEditingPriceValue] = useState('')
  const [editingField, setEditingField] = useState(null)
  const [generatingDesc, setGeneratingDesc] = useState(false)

  const load = async () => {
    const [me, c, p, o] = await Promise.all([
      apiFetch('/auth/me/', { auth, setAuth }),
      apiFetch('/categories/'),
      apiFetch('/products/my-products/', { auth, setAuth }),
      apiFetch('/products/my-orders/?page_size=20', { auth, setAuth }),
    ])

    if (!me.ok || !p.ok) {
      setMsg('Сессия истекла. Войдите заново.')
      return
    }

    setProfile(me.data || null)
    setCategories(getList(c.data))
    setMyProducts(getList(p.data))
    setOrders(getList(o.data))
  }

  useEffect(() => { load() }, [auth.access])

  const addCategory = async (e) => {
    e.preventDefault()
    if (cat.name.trim().length < 2) return setMsg('Название категории должно быть не короче 2 символов')
    const res = await apiFetch('/categories/', { method: 'POST', body: cat, auth, setAuth })
    if (!res.ok) return setMsg(extractError(res.data))
    setMsg('Категория создана')
    setCat({ name: '', description: '' })
    load()
  }

  const generateDescription = async () => {
  if (!form.name.trim()) {
    setMsg('Введите название товара перед генерацией')
    return
  }
  
  setGeneratingDesc(true)
  setMsg('')
  
  try {
    const selected = categories.find((c) => c.id === form.category_id)
    
    const res = await apiFetch('/ai/generate-description/', {
      method: 'POST',
      body: { 
        name: form.name, 
        category: selected?.name || '', 
        specs: parseSpecs(form.specsText) 
      },
      auth,
      setAuth,
    })
    
    if (!res.ok) {
      setMsg(extractError(res.data))
      return
    }
    
    let generatedText = ''
    
    if (res.data.description) {
      // Формат: { description: { ... } }
      if (typeof res.data.description === 'object') {
        // Берем full_description или short_description
        generatedText = res.data.description.full_description || 
                       res.data.description.short_description || 
                       JSON.stringify(res.data.description)
      } 
      // Формат: { description: "текст" }
      else if (typeof res.data.description === 'string') {
        generatedText = res.data.description
      }
    }
    // Формат: { answer: "текст" }
    else if (res.data.answer) {
      generatedText = res.data.answer
    }
    // Формат: { full_description: "текст" }
    else if (res.data.full_description) {
      generatedText = res.data.full_description
    }
    
    if (generatedText) {
      setForm((prev) => ({ 
        ...prev, 
        description: generatedText 
      }))
      setMsg('Описание успешно сгенерировано и добавлено в поле!')
    } else {
      setMsg('Не удалось получить описание. Попробуйте еще раз.')
    }
  } catch (err) {
    setMsg('Ошибка генерации. Попробуйте позже.')
  } finally {
    setGeneratingDesc(false)
  }
}

  const addProduct = async (e) => {
    e.preventDefault()
    if (form.name.trim().length < 2) return setMsg('Название товара должно быть не короче 2 символов')
    if (form.description.trim().length < 10) return setMsg('Описание должно быть не короче 10 символов')
    if (!form.category_id) return setMsg('Выберите категорию')
    
    const priceNum = Number(form.price)
    if (isNaN(priceNum) || priceNum <= 0) {
      return setMsg('Цена должна быть больше нуля')
    }

    const stockNum = Number(form.stock)
    if (!Number.isInteger(stockNum) || stockNum < 0) {
      return setMsg('Количество товара должно быть неотрицательным числом')
    }

    const thresholdNum = form.low_stock_threshold ? Number(form.low_stock_threshold) : 5
    if (!Number.isInteger(thresholdNum) || thresholdNum < 0) {
      return setMsg('Порог низкого остатка должен быть неотрицательным числом')
    }
    
    const res = await apiFetch('/products/', {
      method: 'POST',
      body: {
        name: form.name,
        description: form.description,
        price: priceNum,
        category: form.category_id,
        specs: parseSpecs(form.specsText),
        stock: stockNum,
        low_stock_threshold: thresholdNum
      },
      auth,
      setAuth,
    })
    if (!res.ok) return setMsg(extractError(res.data))
    setMsg('Товар опубликован')
    setForm({ name: '', description: '', price: '', category_id: '', specsText: '', stock: '', low_stock_threshold: '' })
    load()
  }
  
  const startEditingStock = (product) => {
    setEditingProduct(product.id)
    setEditingStockValue(product.stock.toString())
    setEditingField('stock')
  }
  
  const saveStockUpdate = async (productId) => {
    const newStock = parseInt(editingStockValue)
    
    if (isNaN(newStock)) {
      setMsg('Введите корректное число')
      return
    }
    
    if (newStock < 0) {
      setMsg('Количество не может быть отрицательным')
      return
    }
    
    const res = await apiFetch(`/products/my-products/${productId}/`, {
      method: 'PATCH',
      body: { stock: newStock },
      auth,
      setAuth,
    })
    
    if (!res.ok) {
      setMsg(extractError(res.data))
      return
    }
    
    setMsg('Остаток успешно обновлен')
    load()
    cancelEditing()
  }
  
  const startEditingPrice = (product) => {
    setEditingProduct(product.id)
    setEditingPriceValue(product.price.toString())
    setEditingField('price')
  }
  
  const savePriceUpdate = async (productId) => {
    const newPrice = parseFloat(editingPriceValue)
    
    if (isNaN(newPrice)) {
      setMsg('Введите корректную цену')
      return
    }
    
    if (newPrice < 0) {
      setMsg('Цена не может быть отрицательной')
      return
    }
    
    const res = await apiFetch(`/products/my-products/${productId}/`, {
      method: 'PATCH',
      body: { price: newPrice },
      auth,
      setAuth,
    })
    
    if (!res.ok) {
      setMsg(extractError(res.data))
      return
    }
    
    setMsg('Цена успешно обновлена')
    load()
    cancelEditing()
  }
  
  const cancelEditing = () => {
    setEditingProduct(null)
    setEditingStockValue('')
    setEditingPriceValue('')
    setEditingField(null)
  }

  const loadInsights = async () => {
    const res = await apiFetch('/ai/market-insights/', { auth, setAuth })
    if (!res.ok) return setMsg(extractError(res.data))
    setInsights(res.data.insights || '')
    setStats(res.data.stats || null)
  }

  const repeatOrder = async (orderId) => {
    const res = await apiFetch(`/products/orders/${orderId}/repeat/`, {
      method: 'POST',
      auth,
      setAuth,
    })
    if (!res.ok) return setMsg(extractError(res.data))
    setMsg('Товары из заказа добавлены в корзину')
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
          
          <input 
            required 
            type="number" 
            min="0" 
            step="1" 
            placeholder="Количество на складе (шт.)" 
            value={form.stock} 
            onChange={(e) => setForm({ ...form, stock: e.target.value })} 
          />
          <input 
            type="number" 
            min="0" 
            step="1" 
            placeholder="Порог низкого остатка (по умолчанию 5)" 
            value={form.low_stock_threshold} 
            onChange={(e) => setForm({ ...form, low_stock_threshold: e.target.value })} 
          />
          
          <select required value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
            <option value="">Выберите категорию</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <textarea rows={4} placeholder={'Характеристики\nЦвет: Черный\nПамять: 256 ГБ'} value={form.specsText} onChange={(e) => setForm({ ...form, specsText: e.target.value })} />
          <textarea required rows={6} placeholder="Описание" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <div className="actions-row">
            <button 
              className="btn btn-outline" 
              type="button" 
              onClick={generateDescription}
              disabled={generatingDesc}
            >
              {generatingDesc ? 'Генерация...' : 'Сгенерировать описание AI'}
            </button>
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
              
              <div className="price-info">
                {editingProduct === p.id && editingField === 'price' ? (
                  <div className="edit-field">
                    <input 
                      type="number" 
                      value={editingPriceValue}
                      onChange={(e) => setEditingPriceValue(e.target.value)}
                      min="0"
                      step="0.01"
                      autoFocus
                    />
                    <div className="edit-buttons">
                      <button className="btn-save" onClick={() => savePriceUpdate(p.id)}>Сохранить</button>
                      <button className="btn-cancel" onClick={cancelEditing}>Отмена</button>
                    </div>
                  </div>
                ) : (
                  <p className="price">
                    {p.price} ₽
                    <button 
                      className="btn-edit-small" 
                      onClick={() => startEditingPrice(p)}
                      title="Редактировать цену"
                    >
                      ✏️
                    </button>
                  </p>
                )}
              </div>
              
              <div className="stock-info">
                {editingProduct === p.id && editingField === 'stock' ? (
                  <div className="edit-field">
                    <input 
                      type="number" 
                      value={editingStockValue}
                      onChange={(e) => setEditingStockValue(e.target.value)}
                      min="0"
                      step="1"
                      autoFocus
                    />
                    <div className="edit-buttons">
                      <button className="btn-save" onClick={() => saveStockUpdate(p.id)}>Сохранить</button>
                      <button className="btn-cancel" onClick={cancelEditing}>Отмена</button>
                    </div>
                  </div>
                ) : (
                  <p className={`stock-value ${p.stock <= p.low_stock_threshold && p.stock > 0 ? 'low' : ''}`}>
                    В наличии: {p.stock} шт.
                    {p.stock <= p.low_stock_threshold && p.stock > 0 && 
                      <span className="warning"> низкий остаток!</span>
                    }
                    {p.stock === 0 && <span className="out"> закончился</span>}
                    <button 
                      className="btn-edit-small" 
                      onClick={() => startEditingStock(p)}
                      title="Изменить количество"
                    >
                      ✏️
                    </button>
                  </p>
                )}
              </div>
              
              <p className="meta">{p.category?.name}</p>
            </article>
          ))}
        </div>

        <h2 style={{ marginTop: 16 }}>Мои заказы</h2>
        {orders.map((o) => (
          <article className="product-card" key={o.id}>
            <p><b>Заказ #{o.id}</b> · {o.total} ₽ · статус: {o.status}</p>
            <p className="meta">{o.full_name}, {o.phone}, {o.city}, {o.address}</p>
            {o.items?.length > 0 && (
              <ul className="order-items">
                {o.items.map((item) => (
                  <li key={item.id}>{item.product_name} · {item.quantity} шт. · {item.price} ₽</li>
                ))}
              </ul>
            )}
            <div className="actions-row">
              <button className="btn btn-accent" type="button" onClick={() => repeatOrder(o.id)}>
                Повторить заказ
              </button>
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
            <p className="meta">Товаров с низким остатком: {myProducts.filter(p => p.stock > 0 && p.stock <= p.low_stock_threshold).length}</p>
            <p className="meta">Распроданных товаров: {myProducts.filter(p => p.stock === 0).length}</p>
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
  const [loading, setLoading] = useState(false)
  const [checkoutData, setCheckoutData] = useState({ 
    full_name: '', 
    phone: '', 
    city: '', 
    address: '', 
    comment: '' 
  })

  const load = async () => {
    if (!auth.access) return
    const res = await apiFetch('/products/cart/', { auth, setAuth })
    if (!res.ok) return
    setCart({
      items: Array.isArray(res.data.items) ? res.data.items : [],
      total: Number(res.data.total || 0),
    })
  }

  useEffect(() => { 
    if (auth.access) load() 
  }, [auth.access])

  const updateCartQuantity = async (productId, newQuantity) => {
    if (!auth.access) return
    if (loading) return
    
    setLoading(true)
    
    if (newQuantity <= 0) {
      // Удаляем товар из корзины
      const item = cart.items.find(i => i.product.id === productId)
      if (item) {
        const res = await apiFetch(`/products/cart/${item.id}/`, { 
          method: 'DELETE', 
          auth, 
          setAuth 
        })
        if (!res.ok) {
          setMsg(extractError(res.data))
        }
        await load()
      }
      setLoading(false)
      return
    }

    // Проверяем доступность товара
    const product = cart.items.find(i => i.product.id === productId)?.product
    if (product && newQuantity > product.stock) {
      setMsg(`Недостаточно товара. В наличии: ${product.stock} шт.`)
      setLoading(false)
      return
    }

    // Обновляем количество через PATCH эндпоинт
    const res = await apiFetch('/products/cart/update/', {
      method: 'PATCH',
      body: { product_id: productId, quantity: newQuantity },
      auth,
      setAuth,
    })

    if (!res.ok) {
      setMsg(extractError(res.data))
    } else {
      await load()
    }
    
    setLoading(false)
  }

  const removeItem = async (itemId, productId) => {
    await updateCartQuantity(productId, 0)
  }

  const checkout = async () => {
    setMsg('')
    const validationError = validateCheckoutForm(checkoutData)
    if (validationError) return setMsg(validationError)
    setLoading(true)
    
    // Проверяем, что все товары есть в наличии
    const unavailableItems = cart.items.filter(item => item.quantity > item.product.stock)
    if (unavailableItems.length > 0) {
      const names = unavailableItems.map(i => i.product.name).join(', ')
      setMsg(`Товары недоступны в нужном количестве: ${names}. Обновите корзину.`)
      setLoading(false)
      return
    }
    
    const res = await apiFetch('/products/cart/checkout/', { 
      method: 'POST', 
      body: checkoutData, 
      auth, 
      setAuth 
    })
    
    if (!res.ok) {
      if (res.data.error && res.data.error.includes('недоступен')) {
        setMsg(`${res.data.error}. Обновите корзину.`)
        load()
      } else {
        setMsg(extractError(res.data))
      }
      setLoading(false)
      return
    }
    
    setMsg(`Заказ оформлен на сумму ${Number(res.data.order?.total || 0).toFixed(2)} ₽`)
    load()
    // Очищаем форму
    setCheckoutData({ full_name: '', phone: '', city: '', address: '', comment: '' })
    setLoading(false)
  }

  if (!auth.access) {
    return (
      <section className="panel">
        <p>Войдите в аккаунт, чтобы пользоваться корзиной.</p>
      </section>
    )
  }

  return (
    <section className="panel">
      <h2>Корзина</h2>
      {msg && <p className="note">{msg}</p>}
      
      {cart.items.length === 0 ? (
        <p>Корзина пуста</p>
      ) : (
        <>
          <div className="cart-items">
            {cart.items.map((item) => (
              <div className="cart-item" key={item.id}>
                <div className="cart-item-info">
                  <h3>{item.product.name}</h3>
                  <p className="price">{item.product.price} ₽</p>
                  <p className="meta">категория: {item.product.category?.name || 'Без категории'}</p>
                  {item.quantity > item.product.stock && (
                    <p className="error-meta">⚠️ В наличии только {item.product.stock} шт.</p>
                  )}
                </div>
                
                <div className="cart-item-controls">
                  <div className="quantity-controls">
                    <button 
                      className="qty-btn"
                      onClick={() => updateCartQuantity(item.product.id, item.quantity - 1)}
                      disabled={loading}
                    >
                      -
                    </button>
                    <span className="qty-value">{item.quantity}</span>
                    <button 
                      className="qty-btn"
                      onClick={() => updateCartQuantity(item.product.id, item.quantity + 1)}
                      disabled={loading || item.quantity >= item.product.stock}
                    >
                      +
                    </button>
                  </div>
                  <button 
                    className="btn-remove"
                    onClick={() => removeItem(item.id, item.product.id)}
                    disabled={loading}
                  >
                    Удалить
                  </button>
                </div>
                
                <div className="cart-item-total">
                  <span>Сумма: {(item.product.price * item.quantity).toFixed(2)} ₽</span>
                </div>
              </div>
            ))}
          </div>
          
          <div className="cart-summary">
            <h3>Итого: {Number(cart.total).toFixed(2)} ₽</h3>
            
            <div className="form-block">
              <h3>Данные для доставки</h3>
              <input 
                placeholder="ФИО" 
                value={checkoutData.full_name} 
                onChange={(e) => setCheckoutData({ ...checkoutData, full_name: e.target.value })} 
                minLength={3}
                required
              />
              <input 
                placeholder="Телефон" 
                value={checkoutData.phone} 
                onChange={(e) => setCheckoutData({ ...checkoutData, phone: e.target.value })} 
                inputMode="tel"
                pattern="[0-9+()\\-\\s]{7,20}"
                required
              />
              <input 
                placeholder="Город" 
                value={checkoutData.city} 
                onChange={(e) => setCheckoutData({ ...checkoutData, city: e.target.value })} 
                minLength={2}
                required
              />
              <input 
                placeholder="Адрес" 
                value={checkoutData.address} 
                onChange={(e) => setCheckoutData({ ...checkoutData, address: e.target.value })} 
                minLength={10}
                required
              />
              <textarea 
                rows={3} 
                placeholder="Комментарий к заказу" 
                value={checkoutData.comment} 
                onChange={(e) => setCheckoutData({ ...checkoutData, comment: e.target.value })} 
              />
            </div>
            
            <button 
              className="btn btn-accent" 
              onClick={checkout} 
              disabled={
                loading || 
                !cart.items.length || 
                cart.items.some(item => item.quantity > item.product.stock) ||
                !checkoutData.full_name ||
                !checkoutData.phone ||
                !checkoutData.city ||
                !checkoutData.address
              }
            >
              {loading ? 'Обработка...' : 'Оформить заказ'}
            </button>
          </div>
        </>
      )}
    </section>
  )
}


function AIPriceSearchWidget({ auth, setAuth, onAddToCart, onFeedback }) {
  const [query, setQuery] = useState('')
  const [bundleQuery, setBundleQuery] = useState('')
  const [recommendations, setRecommendations] = useState(null)
  const [personalRecommendations, setPersonalRecommendations] = useState(null)
  const [bundle, setBundle] = useState(null)
  const [loading, setLoading] = useState(false)
  const [bundleLoading, setBundleLoading] = useState(false)
  const [error, setError] = useState('')
  const [priceAnalysis, setPriceAnalysis] = useState(null)

  useEffect(() => {
    const loadPriceAnalysis = async () => {
      const res = await apiFetch('/ai/price-analysis/')
      if (res.ok) {
        setPriceAnalysis(res.data)
      }
    }
    loadPriceAnalysis()
  }, [])

  useEffect(() => {
    const loadPersonal = async () => {
      if (!auth?.access) {
        setPersonalRecommendations(null)
        return
      }
      const res = await apiFetch('/ai/personal-recommendations/', { auth, setAuth })
      if (res.ok) setPersonalRecommendations(res.data)
    }
    loadPersonal()
  }, [auth?.access])

  const getRecommendations = async () => {
    if (!query.trim()) return
    
    setLoading(true)
    setError('')
    setRecommendations(null)
    
    try {
      const res = await apiFetch('/ai/semantic-search/', {
        method: 'POST',
        body: { query: query },
        auth,
        setAuth,
      })
      
      if (res.ok) {
        setRecommendations(res.data)
      } else {
        setError(extractError(res.data))
      }
    } catch (err) {
      setError('Ошибка соединения. Попробуйте позже.')
    } finally {
      setLoading(false)
    }
  }

  const getBundle = async () => {
    if (!bundleQuery.trim()) return
    setBundleLoading(true)
    setError('')
    setBundle(null)
    const res = await apiFetch('/ai/bundle/', {
      method: 'POST',
      body: { query: bundleQuery },
      auth,
      setAuth,
    })
    if (res.ok) {
      setBundle(res.data)
    } else {
      setError(extractError(res.data))
    }
    setBundleLoading(false)
  }

  const addBundleToCart = async () => {
    if (!bundle?.items?.length) return
    for (const item of bundle.items) {
      const quantity = Number(item.quantity || 1)
      for (let i = 0; i < quantity; i += 1) {
        await onAddToCart(item.product_id, bundleQuery)
      }
    }
  }

  const renderRecommendationList = (data, title) => {
    if (!data?.recommendations?.length) return null
    return (
      <div className="recommendations-list">
        <div className="list-header">{title}</div>
        {data.recommendations.map((rec, idx) => (
          <div className="recommendation-card" key={`${title}-${rec.product_id}`}>
            <div className="rank-badge">{idx + 1}</div>
            <div className="card-content">
              <div className="card-header">
                <h4>{rec.name}</h4>
                <span className={`price-badge ${rec.price_rating === 'бюджетный' ? 'budget' : rec.price_rating === 'премиум' ? 'premium' : 'medium'}`}>
                  {rec.price_rating || 'подходит'}
                </span>
              </div>
              <div className="price">{Number(rec.price || 0).toLocaleString()} ₽</div>
              <div className="reason">
                <span className="reason-label">Почему подходит:</span>
                <span>{rec.why_fits}</span>
              </div>
              <button className="btn-small" type="button" onClick={() => onAddToCart && onAddToCart(rec.product_id, query)}>
                В корзину
              </button>
            </div>
          </div>
        ))}
        {data.interaction_id && (
          <div className="ai-feedback-row">
            <button className="btn btn-dark-outline" type="button" onClick={() => onFeedback(data.interaction_id, true)}>Помогло</button>
            <button className="btn btn-dark-outline" type="button" onClick={() => onFeedback(data.interaction_id, false, query)}>Не помогло</button>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="ai-price-widget">
      <div className="widget-header">
        <span className="widget-icon">💰</span>
        <h3>AI-поиск и персональные подборки</h3>
      </div>
      
      {priceAnalysis && priceAnalysis.price_range && (
        <div className="price-analysis-banner">
          <div className="price-range">
            <span>📊 Цены в магазине:</span>
            <span className="min-price">от {priceAnalysis.price_range.min}₽</span>
            <span className="max-price">до {priceAnalysis.price_range.max}₽</span>
            <span className="avg-price">средняя {priceAnalysis.price_range.avg}₽</span>
          </div>
          {priceAnalysis.insight && (
            <p className="insight">💡 {priceAnalysis.insight}</p>
          )}
        </div>
      )}
      
      <p className="widget-hint">Опишите задачу обычными словами: AI поймёт смысл, бюджет и сценарий использования</p>
      
      <div className="search-row">
        <textarea
          rows={2}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Например: лёгкий рюкзак для треккинга или ноутбук для работы до 50000 рублей"
          disabled={loading}
        />
        <button 
          className="btn btn-accent"
          onClick={getRecommendations}
          disabled={loading || !query.trim()}
        >
          {loading ? 'Ищем...' : 'Найти по смыслу'}
        </button>
      </div>

      {recommendations?.clarifying_questions?.length > 0 && (
        <div className="ai-followups">
          <b>AI уточняет:</b>
          {recommendations.clarifying_questions.map((question) => (
            <button key={question} className="chip-button" type="button" onClick={() => setQuery(`${query}. ${question}`)}>
              {question}
            </button>
          ))}
        </div>
      )}
      
      {error && <div className="error-message">{error}</div>}
      
      {loading && (
        <div className="loading-state">
          <div className="loading-spinner-small"></div>
          <p>Анализирую запрос, историю и каталог...</p>
        </div>
      )}

      {personalRecommendations && renderRecommendationList(personalRecommendations, 'Персонально для вас')}
      
      {recommendations && (
        <div className="recommendations-result">
          {recommendations.understanding && (
            <div className="understanding-bubble">
              <span className="icon">🤔</span>
              <p>{recommendations.understanding}</p>
            </div>
          )}
          
          {recommendations.budget_found && recommendations.budget_amount && (
            <div className="budget-info">
              <span className="budget-label">Ваш бюджет:</span>
              <span className="budget-value">{recommendations.budget_amount.toLocaleString()} ₽</span>
            </div>
          )}
          
          {recommendations.recommendations && recommendations.recommendations.length > 0 ? (
            renderRecommendationList(recommendations, 'Вот что можно купить')
          ) : (
            <div className="no-results">
              <p>😔 Не нашлось товаров под ваш запрос</p>
              {recommendations.alternative_advice && (
                <p className="advice">{recommendations.alternative_advice}</p>
              )}
            </div>
          )}
          
          {recommendations.budget_advice && (
            <div className="budget-advice">
              <span className="advice-icon">💡</span>
              <span>{recommendations.budget_advice}</span>
            </div>
          )}
        </div>
      )}

      <div className="bundle-builder">
        <div className="widget-header">
          <span className="widget-icon">🎁</span>
          <h3>Собрать комплект</h3>
        </div>
        <div className="search-row">
          <textarea
            rows={2}
            value={bundleQuery}
            onChange={(e) => setBundleQuery(e.target.value)}
            placeholder="Например: собрать комплект к походу или подарок на день рождения"
            disabled={bundleLoading}
          />
          <button className="btn btn-accent" type="button" onClick={getBundle} disabled={bundleLoading || !bundleQuery.trim()}>
            {bundleLoading ? 'Собираю...' : 'Собрать'}
          </button>
        </div>
        {bundle && (
          <div className="bundle-result">
            <h4>{bundle.title}</h4>
            <p className="meta">{bundle.explanation}</p>
            {bundle.clarifying_questions?.length > 0 && (
              <div className="ai-followups">
                {bundle.clarifying_questions.map((question) => (
                  <button key={question} className="chip-button" type="button" onClick={() => setBundleQuery(`${bundleQuery}. ${question}`)}>
                    {question}
                  </button>
                ))}
              </div>
            )}
            {bundle.items?.map((item) => (
              <div className="bundle-item" key={item.product_id}>
                <b>{item.product?.name}</b>
                <span>{item.role}</span>
                <span>{Number(item.product?.price || 0).toLocaleString()} ₽ · {item.quantity} шт.</span>
              </div>
            ))}
            {bundle.items?.length > 0 && (
              <button className="btn btn-accent" type="button" onClick={addBundleToCart}>
                Добавить комплект в корзину
              </button>
            )}
          </div>
        )}
      </div>
    </div>
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
