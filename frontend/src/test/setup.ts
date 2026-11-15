import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import { clearSession } from '../services/api'

// jsdom has no top-layer dialog implementation. Browser focus trapping is native in production.
HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }

afterEach(() => {
  cleanup()
  clearSession()
  document.cookie = 'smartrobot_csrf=; Max-Age=0; Path=/'
})
