import axios from 'axios'

const api = axios.create({
  baseURL: '',
  timeout: 10000,
})

// JWT 토큰 자동 첨부 인터셉터
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 401 응답 시 자동 로그아웃
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user_info')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
