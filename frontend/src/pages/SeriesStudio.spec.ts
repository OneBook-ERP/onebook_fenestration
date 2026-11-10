import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { routes } from '@/router'
import ProfileFormPage from './studio/ProfileFormPage.vue'
import SeriesStudio from './SeriesStudio.vue'

vi.mock('@/studio/api', async (orig) => ({
	...(await orig<object>()),
	saveProfileSeries: vi.fn().mockResolvedValue('CS500'),
	getProfileSeriesDoc: vi.fn().mockResolvedValue({
		name: 'CS400',
		series_code: 'CS400',
		series_title: 'CS400 Economical',
		system_type: 'Casement',
		published_version: 'CS400-V01',
	}),
	getSeriesVersionDoc: vi.fn().mockResolvedValue({
		name: 'CS400-V01',
		series: 'CS400',
		version_note: 'Initial release',
		docstatus: 1,
		deductions: [{ deduction_key: 'sash_w', value: 42 }],
		constants: [{ constant_key: 'glass_bite', value: 12 }],
		member_rules: [
			{
				rule_id: 'frame_top',
				role: 'frame',
				profile: 'LP101-CS400',
				angle_start: 45,
				angle_end: 135,
				length_expr: 'W',
			},
		],
		hardware_rules: [],
		validation_rules: [],
	}),
	getFenestrationProfileDoc: vi.fn().mockResolvedValue({
		name: 'LP101-CS400',
		profile_code: 'LP101-CS400',
		profile_name: 'Outer Frame',
		series: 'CS400',
		role: 'frame',
		item: 'LP101-CS400',
		kg_per_m: 0.785,
		computed_kg_per_m: 0.79,
		use_computed_weight: 1,
		width_mm: 40,
		depth_mm: 45,
		area_mm2: 291.5,
		perimeter_mm: 198,
		total_perimeter_mm: 198,
		visible_perimeter_mm: 160,
		ix_mm4: 48200,
		iy_mm4: 39100,
		bar_lengths: '4880, 5800',
		dxf_file: '/files/LP101.dxf',
		section_svg: 'M 0 0 L 40 0 L 40 45 L 0 45 Z',
		section_warnings: '',
	}),
	previewDxf: vi.fn().mockResolvedValue({
		ok: true,
		section: {
			area_mm2: 310.2,
			width_mm: 42.0,
			depth_mm: 48.0,
			perimeter_mm: 210.5,
			total_perimeter_mm: 210.5,
			ix_mm4: 52000,
			iy_mm4: 41000,
			computed_kg_per_m: 0.841,
			section_svg: 'M 0 0 L 42 0 L 42 48 L 0 48 Z',
			section_warnings: '',
		},
	}),
	createSeriesVersion: vi.fn(),
	updateSeriesVersion: vi.fn(),
	publishSeriesVersion: vi.fn(),
	saveFenestrationProfile: vi.fn(),
	saveFenestrationGlass: vi.fn(),
	setProfileOrientation: vi.fn().mockResolvedValue({
		ok: true,
		profile_name: 'LP101',
		section_rotation: '90',
		width_mm: 45.0,
		depth_mm: 40.0,
	}),
}))

vi.mock('frappe-ui', async (orig) => ({
	...(await orig<object>()),
	upload: vi.fn().mockResolvedValue({
		file_name: 'section.dxf',
		file_size: 1024,
		file_url: '/files/section.dxf',
	}),
	useList: (await import('@/test-utils')).fakeUseList({
		'Profile Series': [
			{
				name: 'CS400',
				series_code: 'CS400',
				series_title: 'CS400 Economical',
				system_type: 'Casement',
				published_version: 'CS400-V01',
			},
			{
				name: 'SL200',
				series_code: 'SL200',
				series_title: 'SL200 Sliding',
				system_type: 'Sliding',
				published_version: null,
			},
		],
		'Series Version': [
			{
				name: 'CS400-V01',
				series: 'CS400',
				version_note: 'Initial release',
				docstatus: 1,
			},
			{
				name: 'SL200-V01',
				series: 'SL200',
				version_note: 'Draft sliding rules',
				docstatus: 0,
			},
		],
		'Fenestration Profile': [
			{
				name: 'LP101-CS400',
				profile_code: 'LP101-CS400',
				profile_name: 'Outer Frame',
				series: 'CS400',
				role: 'frame',
				kg_per_m: 0.785,
				computed_kg_per_m: 0.79,
				use_computed_weight: 1,
				width_mm: 40,
				depth_mm: 45,
				area_mm2: 291.5,
				perimeter_mm: 198,
				bar_lengths: '4880, 5800',
				dxf_file: '/files/LP101.dxf',
				section_svg: 'M 0 0 L 40 0 L 40 45 L 0 45 Z',
			},
		],
		'Fenestration Glass': [
			{
				name: 'CLEAR-5',
				glass_code: 'CLEAR-5',
				glass_name: '5mm Clear Float Glass',
				thickness_mm: 5,
				item: 'CLEAR-5',
			},
		],
		Item: [{ name: 'LP101-CS400', item_name: 'Outer Frame' }],
	}),
}))

describe('SeriesStudio', () => {
	it('renders the 4 tabs and switches between them', async () => {
		const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
		router.push('/series-studio')
		await router.isReady()

		const w = mount(SeriesStudio, { global: { plugins: [router] } })
		expect(w.text()).toContain('Profile Series')

		// Tab 1: Profile Series (List View)
		expect(w.text()).toContain('CS400 Economical')
		expect(w.text()).toContain('SL200 Sliding')
		expect(w.findAll('[data-testid="series-row"]')).toHaveLength(2)

		// Switch to Tab 2: Series Version
		await router.push('/series-studio?tab=versions')
		await flushPromises()
		expect(router.currentRoute.value.query.tab).toBe('versions')
		expect(w.findAll('[data-testid="version-row"]')).toHaveLength(2)
		expect(w.text()).toContain('CS400-V01')
		expect(w.text()).toContain('Draft sliding rules')

		// Switch to Tab 3: Fenestration Profile (Card View)
		await router.push('/series-studio?tab=profiles')
		await flushPromises()
		expect(router.currentRoute.value.query.tab).toBe('profiles')
		expect(w.findAll('[data-testid="profile-card"]')).toHaveLength(1)
		expect(w.text()).toContain('LP101 · Outer Frame')
		expect(w.text()).toContain('0.790 kg/m')
		expect(w.find('[data-testid="add-profile-card"]').exists()).toBe(true)

		// Switch to Tab 4: Fenestration Glass (List View)
		await router.push('/series-studio?tab=glass')
		await flushPromises()
		expect(router.currentRoute.value.query.tab).toBe('glass')
		expect(w.findAll('[data-testid="glass-row"]')).toHaveLength(1)
		expect(w.text()).toContain('5mm Clear Float Glass')
		expect(w.text()).toContain('5 mm')
	})

	it('renders the full-page Fenestration Profile form with DXF drag-and-drop and computed properties', async () => {
		const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
		router.push('/series-studio/profiles/LP101-CS400')
		await router.isReady()

		const w = mount(ProfileFormPage, {
			props: { name: 'LP101-CS400' },
			global: { plugins: [router] },
		})
		await flushPromises()

		expect(w.text()).toContain('Profile Configuration')
		expect(w.text()).toContain('Section (from DXF)')
		expect(w.text()).toContain('Computed Section Properties')
		expect(w.text()).toContain('Visible Perimeter (mm)')
		expect(w.find('[data-testid="dxf-dropzone"]').exists()).toBe(true)
	})
})

