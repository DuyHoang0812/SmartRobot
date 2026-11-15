export type Role = 'USER' | 'ADMIN'

export interface User {
  id: string
  username: string
  email: string
  role: Role
  is_active: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}
