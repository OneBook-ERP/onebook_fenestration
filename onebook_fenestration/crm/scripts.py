"""CRM Form & List Script payloads owned by onebook_fenestration.

Uses Frappe CRM's native `formDialog` (real frappe-ui Dialog, FieldLayout,
FormControl, Select, DatePicker, FormattedInput, and Button components) and
Frappe UI semantic CSS tokens so Dark Mode and Light Mode stay 100% native
without modifying apps/crm.
"""

ENHANCER_BOOTSTRAP_JS = r"""
		const ensureFenUiEnhancer = () => {
			const STYLE_ID = 'fen-crm-ui-style'
			const VERSION = 5
			const css = `
[data-fen-priority] {
	display: inline-flex !important;
	align-items: center;
	gap: 6px;
	padding: 2px 8px 2px 7px;
	border-radius: 9999px;
	font-size: 12px !important;
	line-height: 16px !important;
	font-weight: 500 !important;
	width: fit-content;
	max-width: 100%;
	white-space: nowrap;
	vertical-align: middle;
}
[data-fen-priority]::before {
	content: '';
	width: 6px;
	height: 6px;
	border-radius: 9999px;
	flex-shrink: 0;
}
[data-fen-priority='High'] {
	background: var(--surface-red-2, rgba(239, 68, 68, 0.16)) !important;
	color: var(--ink-red-7, #f87171) !important;
}
[data-fen-priority='High']::before {
	background: var(--surface-red-7, #ef4444);
}
[data-fen-priority='Medium'] {
	background: var(--surface-amber-2, rgba(245, 158, 11, 0.16)) !important;
	color: var(--ink-amber-7, #fbbf24) !important;
}
[data-fen-priority='Medium']::before {
	background: var(--surface-amber-7, #f59e0b);
}
[data-fen-priority='Low'] {
	background: var(--surface-green-2, rgba(16, 185, 129, 0.16)) !important;
	color: var(--ink-green-7, #34d399) !important;
}
[data-fen-priority='Low']::before {
	background: var(--surface-green-7, #10b981);
}
button[data-fen-cta='create-quotation'] {
	background: var(--surface-green-7, #16a34a) !important;
	color: #ffffff !important;
	border: none !important;
	font-weight: 500 !important;
	transition: background-color 140ms ease;
}
button[data-fen-cta='create-quotation']:hover {
	background: var(--surface-green-8, #15803d) !important;
}
button[data-fen-cta='create-quotation'] svg {
	color: #ffffff !important;
}
.fen-view-btn {
	height: 28px;
	padding: 0 10px;
	border-radius: 6px;
	border: none;
	background: var(--surface-gray-2, #2e2e2e);
	color: var(--ink-gray-8, #e5e5e5);
	font-size: 13px;
	font-weight: 500;
	text-decoration: none;
	display: inline-flex;
	align-items: center;
	gap: 5px;
	flex-shrink: 0;
	transition: background-color 140ms ease;
}
.fen-view-btn:hover {
	background: var(--surface-gray-3, #383838);
}
`
			let styleEl = document.getElementById(STYLE_ID)
			if (!styleEl) {
				styleEl = document.createElement('style')
				styleEl.id = STYLE_ID
				document.head.appendChild(styleEl)
			}
			if (window.__fenCrmEnhancerVersion !== VERSION || styleEl.textContent !== css) {
				styleEl.textContent = css
			}

			if (window.__fenCrmEnhancerVersion === VERSION && window.__fenCrmEnhancerScan) {
				window.__fenCrmEnhancerScan()
				return
			}
			window.__fenCrmEnhancerVersion = VERSION

			const PRIORITIES = new Set(['High', 'Medium', 'Low'])

			const setPriorityAttr = (el, val) => {
				if (!el) return
				if (PRIORITIES.has(val)) {
					if (el.dataset.fenPriority !== val) el.dataset.fenPriority = val
				} else if (el.dataset.fenPriority) {
					delete el.dataset.fenPriority
				}
			}

			const scan = () => {
				// 1. Style Priority column cells across ListView & GroupBy tables
				const headers = document.querySelectorAll('div.grid.bg-surface-gray-2')
				headers.forEach((header) => {
					const headerChildren = Array.from(header.children)
					let priorityIdx = -1
					for (let i = 0; i < headerChildren.length; i++) {
						const txt = (headerChildren[i].textContent || '').trim().toLowerCase()
						if (txt === 'priority') {
							priorityIdx = i
							break
						}
					}
					if (priorityIdx < 0) return
					const container = header.parentElement
					if (!container) return
					const rows = container.querySelectorAll('div.grid[style*="grid-template-columns"]')
					rows.forEach((row) => {
						if (row === header) return
						const cell = row.children[priorityIdx]
						if (!cell) return
						const target = cell.querySelector('.truncate') || cell
						const val = (target.textContent || '').trim()
						setPriorityAttr(target, val)
					})
				})

				// 2. Style Priority badges inside Kanban cards
				const kanbanFields = document.querySelectorAll('[data-column] [data-name] .truncate')
				kanbanFields.forEach((el) => {
					if (el.children.length > 0) return
					const val = (el.textContent || '').trim()
					if (PRIORITIES.has(val)) setPriorityAttr(el, val)
					else if (el.dataset.fenPriority) delete el.dataset.fenPriority
				})

				// 3. Tag navbar "Create Quotation" action button as solid green Frappe UI CTA
				document.querySelectorAll('header button').forEach((btn) => {
					const txt = (btn.textContent || '').trim()
					if (txt === 'Create Quotation' || txt === __('Create Quotation')) {
						if (btn.dataset.fenCta !== 'create-quotation') {
							btn.dataset.fenCta = 'create-quotation'
						}
					} else if (btn.dataset.fenCta === 'create-quotation') {
						delete btn.dataset.fenCta
					}
				})
			}

			window.__fenCrmEnhancerScan = scan

			if (!window.__fenCrmEnhancerObserver) {
				let rafId = 0
				const schedule = () => {
					if (rafId) return
					rafId = window.requestAnimationFrame(() => {
						rafId = 0
						if (window.__fenCrmEnhancerScan) window.__fenCrmEnhancerScan()
					})
				}
				const obs = new MutationObserver(schedule)
				obs.observe(document.body, {
					childList: true,
					subtree: true,
					characterData: true,
				})
				window.__fenCrmEnhancerObserver = obs
			}
			scan()
		}
"""

DEAL_QUOTATION_SCRIPT_NAME = "OneBook Fenestration Deal Quotation"
LEAD_LIST_UI_SCRIPT_NAME = "OneBook Fenestration Lead List UI"
DEAL_LIST_UI_SCRIPT_NAME = "OneBook Fenestration Deal List UI"
TASK_LIST_UI_SCRIPT_NAME = "OneBook Fenestration Task List UI"
LEAD_FORM_UI_SCRIPT_NAME = "OneBook Fenestration Lead Form UI"

DEAL_QUOTATION_FORM_SCRIPT = (
	r"""class CRMDeal {
	onLoad() {
"""
	+ ENHANCER_BOOTSTRAP_JS
	+ r"""
		ensureFenUiEnhancer()
		if (this.doc.__newDocument) return

		const dealId = this.doc.name
		const self = this
		const PARTNER_VALUES = ['Dealer', 'Fabrication Partner', 'Own Client']

		const formatMoney = (amount, currency) => {
			const num = Number(amount) || 0
			try {
				return new Intl.NumberFormat(undefined, {
					style: 'currency',
					currency: currency || 'INR',
					maximumFractionDigits: 2,
				}).format(num)
			} catch {
				return (currency || 'INR') + ' ' + num.toFixed(2)
			}
		}

		const STATUS_BADGE = {
			Draft: { bg: 'var(--surface-gray-2)', fg: 'var(--ink-gray-7)' },
			Open: { bg: 'var(--surface-blue-2)', fg: 'var(--ink-blue-7)' },
			Replied: { bg: 'var(--surface-blue-2)', fg: 'var(--ink-blue-7)' },
			Ordered: { bg: 'var(--surface-green-2)', fg: 'var(--ink-green-7)' },
			'Partially Ordered': { bg: 'var(--surface-amber-2)', fg: 'var(--ink-amber-7)' },
			Lost: { bg: 'var(--surface-red-2)', fg: 'var(--ink-red-7)' },
			Cancelled: { bg: 'var(--surface-red-2)', fg: 'var(--ink-red-7)' },
			Expired: { bg: 'var(--surface-amber-2)', fg: 'var(--ink-amber-7)' },
		}

		const PARTNER_BADGE = {
			Dealer: { bg: 'var(--surface-green-2)', fg: 'var(--ink-green-7)' },
			'Fabrication Partner': { bg: 'var(--surface-blue-2)', fg: 'var(--ink-blue-7)' },
			'Own Client': { bg: 'var(--surface-violet-2)', fg: 'var(--ink-violet-7)' },
		}

		const getWonStatuses = async () => {
			if (Array.isArray(window.__fenWonDealStatuses)) return window.__fenWonDealStatuses
			try {
				const rows = await call('frappe.client.get_list', {
					doctype: 'CRM Deal Status',
					filters: { type: 'Won' },
					fields: ['name'],
					limit_page_length: 50,
				})
				const names = Array.isArray(rows) ? rows.map((r) => r.name).filter(Boolean) : ['Won']
				window.__fenWonDealStatuses = names.length ? names : ['Won']
			} catch {
				window.__fenWonDealStatuses = ['Won']
			}
			return window.__fenWonDealStatuses
		}

		const getCanCreateQuotation = async () => {
			if (typeof window.__fenCanCreateQuotation === 'boolean') return window.__fenCanCreateQuotation
			try {
				const allowed = await call('crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings.can_create_quotations')
				window.__fenCanCreateQuotation = Boolean(allowed)
			} catch {
				window.__fenCanCreateQuotation = false
			}
			return window.__fenCanCreateQuotation
		}

		const openQuotationDialog = async () => {
			let preview
			try {
				preview = await call('onebook_fenestration.crm.quotation.get_deal_quotation_preview', {
					crm_deal: dealId,
				})
			} catch (err) {
				toast.error(err?.messages?.[0] || err?.message || __('Could not load deal quotation preview'))
				return
			}
			if (!preview) return
			if (!preview.is_confirmed) {
				toast.error(__('Only Won deals can create a Quotation.'))
				return
			}

			const dealer = preview.dealer || {}
			const currency = preview.currency || 'INR'
			const initialItems =
				Array.isArray(preview.items) && preview.items.length
					? preview.items
					: [
							{
								item_code: '',
								item_name: 'Fenestration Package — ' + (preview.deal_name || dealId),
								description: '',
								qty: 1,
								rate: 0,
							},
						]
			const contactSummary =
				[dealer.contact_display, dealer.contact_mobile, dealer.contact_email].filter(Boolean).join(' · ') || '—'
			const defaultPartnerType = PARTNER_VALUES.includes(dealer.partner_type) ? dealer.partner_type : 'Dealer'

			const enhanceGridRow = (row) => {
				if (!row || row.__fenEnhanced) return row
				row.__fenEnhanced = true
				let _itemCode = row.item_code || ''
				Object.defineProperty(row, 'item_code', {
					enumerable: true,
					configurable: true,
					get() {
						return _itemCode
					},
					set(val) {
						const next = val || ''
						const changed = next !== _itemCode
						_itemCode = next
						if (changed && next) {
							call('onebook_fenestration.crm.quotation.get_item_quotation_defaults', {
								item_code: next,
								currency,
							})
								.then((info) => {
									if (!info || _itemCode !== next) return
									row.item_name = info.item_name || next
									row.description = info.description || info.item_name || next
									if (info.uom) row.uom = info.uom
									if (!Number(row.qty)) row.qty = 1
									if (info.rate !== undefined && info.rate !== null) {
										row.rate = Number(info.rate) || 0
									}
								})
								.catch(() => {})
						}
					},
				})
				Object.defineProperty(row, 'amount', {
					enumerable: true,
					configurable: true,
					get() {
						return Math.round((Number(this.qty) || 0) * (Number(this.rate) || 0) * 100) / 100
					},
					set() {},
				})
				return row
			}

			const draftItems = initialItems.map((row, idx) =>
				enhanceGridRow({
					name: 'fen-row-' + (idx + 1),
					idx: idx + 1,
					doctype: 'Quotation Item',
					parentfield: 'items',
					parenttype: 'Quotation',
					__islocal: true,
					item_code: row.item_code || '',
					item_name: row.item_name || row.description || '',
					description: row.description || row.item_name || '',
					qty: Number(row.qty) || 1,
					rate: Number(row.rate) || 0,
				}),
			)

			const rawPush = Array.prototype.push
			Object.defineProperty(draftItems, 'push', {
				enumerable: false,
				configurable: true,
				value(...args) {
					const prepared = args.map((r) => {
						if (r && typeof r === 'object') {
							if (!Number(r.qty)) r.qty = 1
							if (r.rate === '' || r.rate === undefined || r.rate === null) r.rate = 0
							return enhanceGridRow(r)
						}
						return r
					})
					return rawPush.apply(this, prepared)
				},
			})

			await formDialog({
				title: __('Create Quotation'),
				doctype: 'Quotation',
				size: '3xl',
				submitLabel: __('Create Quotation'),
				defaults: {
					currency,
					deal_display: (preview.deal_name || dealId) + ' (' + dealId + ')',
					customer_display: dealer.customer_name || preview.deal_name || dealId,
					contact_display: contactSummary,
					partner_type: defaultPartnerType,
					valid_till: preview.valid_till || '',
					items: draftItems,
					terms: '',
				},
				required: ['partner_type', 'items'],
				tabs: [
					{
						name: 'main',
						label: '',
						sections: [
							{
								name: 'summary_section',
								label: '',
								hideLabel: true,
								hideBorder: true,
								collapsible: false,
								columns: [
									{
										name: 'summary_col_1',
										fields: [
											{ fieldname: 'deal_display', fieldtype: 'Read Only', label: __('Deal') },
										],
									},
									{
										name: 'summary_col_2',
										fields: [
											{ fieldname: 'customer_display', fieldtype: 'Read Only', label: __('Customer / Party') },
										],
									},
									{
										name: 'summary_col_3',
										fields: [
											{ fieldname: 'contact_display', fieldtype: 'Read Only', label: __('Primary Contact') },
										],
									},
								],
							},
							{
								name: 'details_section',
								label: __('Quotation Details'),
								collapsible: false,
								columns: [
									{
										name: 'details_col_1',
										fields: [
											{
												fieldname: 'partner_type',
												fieldtype: 'Select',
												label: __('Customer Type'),
												options: 'Dealer\nFabrication Partner\nOwn Client',
												reqd: 1,
											},
										],
									},
									{
										name: 'details_col_2',
										fields: [
											{ fieldname: 'valid_till', fieldtype: 'Date', label: __('Valid Till') },
										],
									},
								],
							},
							{
								name: 'items_section',
								label: '',
								hideLabel: true,
								collapsible: false,
								columns: [
									{
										name: 'items_col_1',
										fields: [
											{
												fieldname: 'items',
												fieldtype: 'Table',
												label: __('Items'),
												options: 'Quotation Item',
												reqd: 1,
											},
										],
									},
								],
							},
							{
								name: 'terms_section',
								label: '',
								hideLabel: true,
								collapsible: false,
								columns: [
									{
										name: 'terms_col_1',
										fields: [
											{ fieldname: 'terms', fieldtype: 'Small Text', label: __('Terms and Conditions') },
										],
									},
								],
							},
						],
					},
				],
				async onSubmit(data) {
					const rawRows = Array.isArray(data.items) ? data.items : []
					const payloadItems = rawRows
						.map((row) => ({
							item_code: String(row.item_code || '').trim(),
							item_name: String(row.item_name || row.description || row.item_code || '').trim(),
							description: String(row.description || row.item_name || row.item_code || '').trim(),
							qty: Number(row.qty) || 1,
							rate: Number(row.rate) || 0,
						}))
						.filter((r) => r.item_code || r.item_name)

					if (!payloadItems.length) {
						throw new Error(__('Please add at least one item to the quotation.'))
					}
					const total = payloadItems.reduce(
						(acc, r) => acc + (Number(r.qty) || 0) * (Number(r.rate) || 0),
						0,
					)
					const res = await call('onebook_fenestration.crm.quotation.create_quotation_from_deal', {
						crm_deal: dealId,
						valid_till: data.valid_till || '',
						partner_type: data.partner_type || 'Dealer',
						quotation_value: total,
						terms: data.terms || '',
						items: JSON.stringify(payloadItems),
					})
					toast.success(__('Quotation {0} created', [res.name]))
					window.dispatchEvent(new CustomEvent('fen:deal-quotation-created', { detail: { crm_deal: dealId } }))
					return res
				},
			})
		}

		const syncDealNavbarActions = async (explicitStatus) => {
			const [wonStatuses, canCreate] = await Promise.all([
				getWonStatuses(),
				getCanCreateQuotation(),
			])
			const currentStatus = explicitStatus !== undefined ? explicitStatus : self.doc.status
			const isWon = Boolean(currentStatus && wonStatuses.includes(currentStatus))

			const nextActions = (self.actions || []).filter((a) => a && a.label !== __('Create Quotation'))
			if (isWon && canCreate) {
				nextActions.unshift({
					label: __('Create Quotation'),
					icon: 'lucide-file-text',
					onClick: () => openQuotationDialog(),
				})
			}
			self.actions = nextActions

			window.dispatchEvent(
				new CustomEvent('fen:deal-status-changed', {
					detail: { crm_deal: dealId, status: currentStatus, is_confirmed: isWon, can_create: canCreate },
				}),
			)
			ensureFenUiEnhancer()
		}

		this._syncDealNavbarActions = syncDealNavbarActions

		// Patch built-in Quotations tab in place with dark/light Frappe UI native cards & View button
		const QuotationsTab = {
			name: 'FenestrationQuotationsTab',
			props: ['doctype', 'docname', 'doc', 'tab'],
			data() {
				return {
					loading: true,
					rows: [],
					canCreate: false,
					isConfirmed: false,
				}
			},
			mounted() {
				this.load()
				this._onSocket = (data) => {
					if (!data || data.crm_deal === this.docname) this.load()
				}
				this._onLocal = (ev) => {
					if (!ev?.detail || ev.detail.crm_deal === this.docname) this.load()
				}
				this._onStatus = (ev) => {
					if (ev?.detail && ev.detail.crm_deal === this.docname) {
						this.isConfirmed = Boolean(ev.detail.is_confirmed)
						if (typeof ev.detail.can_create === 'boolean') this.canCreate = ev.detail.can_create
					}
				}
				if (socket && socket.on) socket.on('crm_quotation_update', this._onSocket)
				window.addEventListener('fen:deal-quotation-created', this._onLocal)
				window.addEventListener('fen:deal-status-changed', this._onStatus)
			},
			beforeUnmount() {
				if (socket && socket.off) socket.off('crm_quotation_update', this._onSocket)
				window.removeEventListener('fen:deal-quotation-created', this._onLocal)
				window.removeEventListener('fen:deal-status-changed', this._onStatus)
			},
			methods: {
				async load() {
					this.loading = true
					try {
						const [rows, preview] = await Promise.all([
							call('onebook_fenestration.crm.quotation.get_deal_quotations', {
								crm_deal: this.docname,
							}),
							call('onebook_fenestration.crm.quotation.get_deal_quotation_preview', {
								crm_deal: this.docname,
							}).catch(() => null),
						])
						this.rows = Array.isArray(rows) ? rows : []
						this.canCreate = Boolean(preview && preview.can_create_quotations)
						this.isConfirmed = Boolean(preview && preview.is_confirmed)
					} finally {
						this.loading = false
					}
				},
			},
			render() {
				if (this.loading && !this.rows.length) {
					return h('div', { style: 'padding:48px 24px;text-align:center;color:var(--ink-gray-5);font-size:13px;' }, __('Loading...'))
				}

				if (!this.rows.length) {
					return h('div', { style: 'display:flex;flex-direction:column;height:100%;' }, [
						h(
							'div',
							{ style: 'padding:64px 24px;text-align:center;color:var(--ink-gray-5);display:flex;flex-direction:column;align-items:center;gap:6px;' },
							[
								h('div', { style: 'font-size:14px;font-weight:500;color:var(--ink-gray-8);' }, __('No quotations yet')),
								h(
									'div',
									{ style: 'font-size:13px;color:var(--ink-gray-5);max-width:360px;' },
									this.isConfirmed
										? __('Use Create Quotation in the top bar to generate a quotation for this Won deal.')
										: __('Change this deal status to Won to enable Create Quotation.'),
								),
							],
						),
					])
				}

				const cards = this.rows.map((q, idx) => {
					const st = STATUS_BADGE[q.status] || STATUS_BADGE.Draft
					const pt = PARTNER_BADGE[q.partner_type] || PARTNER_BADGE.Dealer
					const dealLabel = q.deal_name || q.crm_deal || ''
					const custLabel = q.customer_name || q.party_name || ''
					const showCustomer = custLabel && custLabel !== dealLabel
					const contactText = [q.contact_display, q.contact_mobile].filter(Boolean).join(' · ')
					const dateText = q.valid_till
						? __('Valid till {0}', [q.valid_till])
						: q.transaction_date || ''
					return h('div', { key: q.name }, [
						h(
							'div',
							{
								style: 'display:flex;align-items:center;justify-content:space-between;gap:14px;padding:12px 14px;border-radius:8px;',
							},
							[
								h(
									'a',
									{
										href: q.url,
										target: '_blank',
										rel: 'noopener noreferrer',
										style: 'display:flex;flex-direction:column;gap:5px;flex:1;min-width:0;text-decoration:none;color:inherit;',
									},
									[
										h('div', { style: 'display:flex;flex-wrap:wrap;align-items:center;gap:8px;' }, [
											h('span', { style: 'font-weight:500;font-size:14px;color:var(--ink-gray-9);' }, q.name),
											h(
												'span',
												{
													style: 'font-size:12px;font-weight:500;padding:2px 8px;border-radius:9999px;background:' + st.bg + ';color:' + st.fg + ';',
												},
												q.status || 'Draft',
											),
											q.partner_type
												? h(
														'span',
														{
															style: 'font-size:12px;font-weight:500;padding:2px 8px;border-radius:9999px;background:' + pt.bg + ';color:' + pt.fg + ';',
														},
														q.partner_type,
													)
												: null,
										]),
										h('div', { style: 'display:flex;flex-wrap:wrap;align-items:center;gap:6px;font-size:13px;color:var(--ink-gray-6);' }, [
											dealLabel ? h('span', { style: 'font-weight:500;color:var(--ink-gray-8);' }, dealLabel) : null,
											showCustomer && dealLabel ? h('span', { style: 'color:var(--ink-gray-4);' }, '·') : null,
											showCustomer ? h('span', null, custLabel) : null,
											contactText ? h('span', { style: 'color:var(--ink-gray-4);' }, '·') : null,
											contactText ? h('span', { style: 'color:var(--ink-gray-5);' }, contactText) : null,
										]),
										h('div', { style: 'display:flex;align-items:center;gap:6px;font-size:13px;color:var(--ink-gray-6);' }, [
											h(
												'span',
												{ style: 'font-weight:600;color:var(--ink-gray-9);font-variant-numeric:tabular-nums;' },
												formatMoney(q.rounded_total || q.grand_total, q.currency),
											),
											dateText ? h('span', { style: 'color:var(--ink-gray-4);' }, '·') : null,
											dateText ? h('span', null, dateText) : null,
										]),
									],
								),
								h(
									'a',
									{
										href: q.url,
										target: '_blank',
										rel: 'noopener noreferrer',
										class: 'fen-view-btn',
									},
									[
										h('span', null, __('View')),
										h(
											'svg',
											{
												width: '13',
												height: '13',
												viewBox: '0 0 24 24',
												fill: 'none',
												stroke: 'currentColor',
												'stroke-width': '1.75',
												'stroke-linecap': 'round',
												'stroke-linejoin': 'round',
											},
											[
												h('path', { d: 'M7 7h10v10' }),
												h('path', { d: 'M7 17 17 7' }),
											],
										),
									],
								),
							],
						),
						idx < this.rows.length - 1
							? h('div', { style: 'height:1px;background:var(--outline-gray-1);margin:0 14px;' })
							: null,
					])
				})

				return h('div', { style: 'display:flex;flex-direction:column;height:100%;' }, [
					h('div', { style: 'padding:12px 16px 20px 16px;' }, cards),
				])
			},
		}

		this.tabs.push({
			name: 'Quotations',
			component: QuotationsTab,
		})

		syncDealNavbarActions(this.doc.status)

		call('crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings.get_customer_link', {
			crm_deal: dealId,
		})
			.then((customerUrl) => {
				if (!customerUrl) return
				const existing = [...(self.actions || [])]
				if (!existing.some((a) => a && a.label === __('View Customer'))) {
					let safeCustomerUrl = customerUrl
					try {
						const parsed = new URL(customerUrl, window.location.origin)
						if (parsed.pathname.startsWith('/desk/') || parsed.pathname.startsWith('/app/')) {
							safeCustomerUrl = parsed.pathname + parsed.search
						}
					} catch {
						safeCustomerUrl = customerUrl
					}
					existing.push({
						label: __('View Customer'),
						onClick: () => window.open(safeCustomerUrl, '_blank'),
					})
					self.actions = existing
				}
			})
			.catch(() => {})
	}

	onRender() {
		if (this._syncDealNavbarActions) this._syncDealNavbarActions(this.doc.status)
	}

	status() {
		if (this._syncDealNavbarActions) this._syncDealNavbarActions(this.value !== undefined ? this.value : this.doc.status)
	}

	onSave() {
		if (this._syncDealNavbarActions) this._syncDealNavbarActions(this.doc.status)
	}
}
"""
)

LIST_UI_ENHANCER_SCRIPT = (
	r"""function setupList() {
"""
	+ ENHANCER_BOOTSTRAP_JS
	+ r"""
	ensureFenUiEnhancer()
	return {}
}
"""
)

LEAD_FORM_UI_SCRIPT = (
	r"""class CRMLead {
	onLoad() {
"""
	+ ENHANCER_BOOTSTRAP_JS
	+ r"""
		ensureFenUiEnhancer()
	}
}
"""
)
