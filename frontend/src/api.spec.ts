import { call } from 'frappe-ui'
import { describe, expect, it, vi } from 'vitest'
import { getSession } from './api'

vi.mock('frappe-ui', () => ({ call: vi.fn() }))

describe('getSession', () => {
	it('loads roles with get_current_user_roles', async () => {
		vi.mocked(call).mockImplementation(async (method: string) =>
			method === 'frappe.auth.get_logged_user' ? 'a@b.c' : ['Sales User'],
		)
		expect(await getSession()).toEqual({ user: 'a@b.c', roles: ['Sales User'] })
		expect(vi.mocked(call).mock.calls.map((c) => c[0])).toEqual([
			'frappe.auth.get_logged_user',
			'frappe.core.doctype.user.user.get_current_user_roles',
		])
	})
})
