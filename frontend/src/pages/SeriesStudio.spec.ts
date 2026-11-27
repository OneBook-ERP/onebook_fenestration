import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { routes } from '@/router'
import ProfileFormPage from './studio/ProfileFormPage.vue'
import GlassFormPage from './studio/GlassFormPage.vue'
import GlazingConfigPage from './studio/GlazingConfigPage.vue'
import HardwareFormPage from './studio/HardwareFormPage.vue'
import SeriesVersionFormPage from './studio/SeriesVersionFormPage.vue'
import SeriesSectionConfigPage from './studio/SeriesSectionConfigPage.vue'
import SeriesStudio from './SeriesStudio.vue'

vi.mock('@/api', async (orig) => ({
	...(await orig<object>()),
	crossSection: vi.fn().mockResolvedValue({
		ok: true,
		result: {
			axis: 'h',
			at: 600,
			length: 1200,
			pieces: [
				{ kind: 'profile', code: 'E104156', role: 'frame', panel: 'F1', start: 0, end: 42, mirrored: false, thickness: 0 },
				{ kind: 'profile', code: 'CS4807-CS400', role: 'bead', panel: 'F1', start: 22, end: 45, mirrored: false, thickness: 0 },
				{ kind: 'glass', code: '6CTG', role: 'glass', panel: 'F1', start: 42, end: 1158, mirrored: false, thickness: 6 },
				{ kind: 'profile', code: 'CS4807-CS400', role: 'bead', panel: 'F1', start: 1155, end: 1178, mirrored: true, thickness: 0 },
				{ kind: 'profile', code: 'E104156', role: 'frame', panel: 'F1', start: 1158, end: 1200, mirrored: true, thickness: 0 },
			],
			dims: [],
			issues: [],
		},
		outlines: {
			E104156: { svg: 'M 0 0 L 42 0 L 42 40 L 0 40 Z', width: 42, depth: 40 },
			'CS4807-CS400': { svg: 'M 0 0 L 23 0 L 23 24 L 0 24 Z', width: 23, depth: 24 },
		},
	}),
}))

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
				angle_end: 45,
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
	getFenestrationHardwareDoc: vi.fn().mockResolvedValue({
		name: 'G22',
		hardware_code: 'G22',
		hardware_name: 'Glazing Gasket 2mm',
		category: 'Gasket',
		uom: 'Meter',
		thickness_mm: 2,
		width_mm: 4.5,
		depth_mm: 10.7,
		section_svg: 'M 0 0 L 4.5 0 L 4.5 10.7 L 0 10.7 Z',
	}),
	saveFenestrationHardware: vi.fn().mockResolvedValue({
		name: 'G23',
		hardware_code: 'G23',
		hardware_name: 'Glazing Gasket 3mm',
		category: 'Gasket',
	}),
	getGlobalGlazingRules: vi.fn().mockResolvedValue({
		ok: true,
		rules: [
			{
				id: 'std_6_8',
				label: '6-8mm Glass',
				min_glass_mm: 6,
				max_glass_mm: 8.5,
				host: 'both',
				bead_profile: 'CS4807',
				bead_side: 'inside',
				inner_gasket_hardware: 'G24',
				inner_gasket_item: 'G24',
				inner_gasket_name: 'Glazing Gasket 4mm',
				outer_gasket_hardware: 'G23',
				outer_gasket_item: 'G23',
				outer_gasket_name: 'Glazing Gasket 3mm',
			},
		],
		auto_config: {
			enabled: true,
			max_compression_mm: 1,
			loose_tolerance_mm: 0.05,
			thicker_gasket_side: 'outer',
			gasket_pool: [],
			channels: [],
		},
		series_list: [
			{ name: 'CS400', series_code: 'CS400', series_title: 'CS400 Economical', system_type: 'Casement' },
			{ name: 'CS4800', series_code: 'CS4800', series_title: 'CS4800 Heavy', system_type: 'Casement' },
		],
		beads: [
			{ name: 'CS4807-CS400', profile_code: 'CS4807-CS400', profile_name: '6 & 8mm Bead', series: 'CS400', role: 'bead', width_mm: 23, depth_mm: 24, section_svg: 'M 0 0 L 23 0 L 23 24 L 0 24 Z' },
		],
		hardware: [
			{ name: 'G22', hardware_code: 'G22', hardware_name: 'Glazing Gasket 2mm', category: 'Gasket', item: 'G22', thickness_mm: 2, width_mm: 4.5, depth_mm: 10.7, section_svg: 'M 0 0 L 4.5 0 L 4.5 10.7 L 0 10.7 Z' },
			{ name: 'G23', hardware_code: 'G23', hardware_name: 'Glazing Gasket 3mm', category: 'Gasket', item: 'G23', thickness_mm: 3, width_mm: 6.3, depth_mm: 11.2, section_svg: 'M 0 0 L 6.3 0 L 6.3 11.2 L 0 11.2 Z' },
			{ name: 'G24', hardware_code: 'G24', hardware_name: 'Glazing Gasket 4mm', category: 'Gasket', item: 'G24', thickness_mm: 4, width_mm: 6.0, depth_mm: 10.7, section_svg: 'M 0 0 L 6.0 0 L 6.0 10.7 L 0 10.7 Z' },
			{ name: 'G25', hardware_code: 'G25', hardware_name: 'Glazing Gasket 5mm', category: 'Gasket', item: 'G25', thickness_mm: 5, width_mm: 7.5, depth_mm: 9.2, section_svg: 'M 0 0 L 7.5 0 L 7.5 9.2 L 0 9.2 Z' },
		],
		gasket_items: [{ name: 'G22', item_name: 'Glazing Gasket 2mm' }],
		glasses: [
			{ name: '5CTG', glass_code: '5CTG', glass_name: '5mm Clear', thickness_mm: 5 },
			{ name: '6CTG', glass_code: '6CTG', glass_name: '6mm Clear', thickness_mm: 6 },
		],
	}),
	saveGlobalGlazingRules: vi.fn().mockImplementation(async (rules: unknown, auto_config?: unknown) => ({
		ok: true,
		rules,
		auto_config,
	})),
	getSeriesSectionConfig: vi.fn().mockResolvedValue({
		ok: true,
		series: {
			name: 'CS400',
			series_code: 'CS400',
			series_title: 'CS400 Economical',
			system_type: 'Casement',
			published_version: 'CS400-V01',
		},
		config: {
			version: 1,
			presets: {
				'fixed:window': {
					frame: {
						profile: 'E104156',
						gasket_slot: { x: 12, y: 10, side: 'outside', gasket_item: 'G21', gasket_name: 'Frame Gasket', thickness_mm: 3, configured: true },
						bead_slot: { x: 18, y: 24, side: 'inside', rotation: 0, flip_x: false, flip_y: false, configured: true },
						glass_slot: { x: 24, y: 18, rebate_depth_mm: 12, clearance_mm: 4, configured: true },
					},
					sash: {
						profile: 'E104160',
						rebate_gasket_slot: { x: 0, y: 0, side: 'outside', gasket_item: '', gasket_name: '', thickness_mm: 3, configured: false },
						glazing_gasket_slot: { x: 0, y: 0, side: 'outside', gasket_item: '', gasket_name: '', thickness_mm: 3, configured: false },
						bead_slot: { x: 0, y: 0, side: 'inside', rotation: 0, flip_x: false, flip_y: false, configured: false },
						glass_slot: { x: 0, y: 0, rebate_depth_mm: 12, clearance_mm: 4, configured: false },
						seat_offset_along: 0,
						seat_offset_depth: 0,
						interlock_profile: '',
						track_count: 2,
					},
					bead_gasket_rules: [],
				},
			},
		},
		profiles: [
			{ name: 'E104156', profile_code: 'E104156', profile_name: '40mm Casement Frame', series: 'CS400', role: 'frame', profile_type: 'Window', width_mm: 42, depth_mm: 40, section_svg: 'M 0 0 L 42 0 L 42 40 L 0 40 Z', kg_per_m: 0.65, bar_lengths: '4880' },
			{ name: 'CS4805', profile_code: 'CS4805', profile_name: '48mm Door Frame', series: 'CS400', role: 'frame', profile_type: 'Door', width_mm: 52, depth_mm: 48, section_svg: 'M 0 0 L 52 0 L 52 48 L 0 48 Z', kg_per_m: 0.95, bar_lengths: '4880' },
			{ name: 'E104160', profile_code: 'E104160', profile_name: '40mm Casement Shutter', series: 'CS400', role: 'sash', profile_type: 'Window', width_mm: 64.5, depth_mm: 40, section_svg: 'M 0 0 L 64 0 L 64 40 L 0 40 Z', kg_per_m: 0.95, bar_lengths: '4880' },
			{ name: 'CS4804', profile_code: 'CS4804', profile_name: '48mm Door Shutter', series: 'CS400', role: 'sash', profile_type: 'Door', width_mm: 92, depth_mm: 48, section_svg: 'M 0 0 L 92 0 L 92 48 L 0 48 Z', kg_per_m: 1.45, bar_lengths: '4880' },
			{ name: 'CS4807-CS400', profile_code: 'CS4807-CS400', profile_name: '6 & 8mm Glass Beading (CS400)', series: 'CS400', role: 'bead', width_mm: 23, depth_mm: 24, section_svg: 'M 0 0 L 23 0 L 23 24 L 0 24 Z', kg_per_m: 0.23, bar_lengths: '4880' },
		],
		glasses: [
			{
				name: '6CTG',
				glass_code: '6CTG',
				glass_name: '6 mm clear toughened',
				thickness_mm: 6,
				glazing_rules: [
					{
						series: 'CS400',
						host: 'both',
						bead_profile: 'CS4807-CS400',
						bead_side: 'inside',
						inner_gasket_item: 'G22',
						inner_gasket_name: 'Glazing Gasket 6mm',
						outer_gasket_item: 'G21',
						outer_gasket_name: 'Frame Gasket Casement',
					},
				],
			},
		],
		gaskets: [
			{ name: 'G21', item_name: 'Frame Gasket Casement' },
			{ name: 'G22', item_name: 'Glazing Gasket 6mm' },
		],
	}),
	saveSeriesSectionConfig: vi.fn().mockImplementation(async (series: string, config: unknown) => ({ ok: true, series, config })),
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
				width_mm: 45,
				depth_mm: 40,
				area_mm2: 291.5,
				perimeter_mm: 198,
				bar_lengths: '4880, 5800',
				dxf_file: '/files/LP101.dxf',
				section_svg: 'M 0 0 L 40 0 L 40 45 L 0 45 Z',
				section_rotation: '90',
				section_flip_x: 1,
				section_flip_y: 0,
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
		'Fenestration Hardware': [
			{
				name: 'G22',
				hardware_code: 'G22',
				hardware_name: 'Glazing Gasket 2mm',
				category: 'Gasket',
				uom: 'Meter',
				thickness_mm: 2,
				width_mm: 4.5,
				depth_mm: 10.7,
				section_svg: 'M 0 0 L 4.5 0 L 4.5 10.7 L 0 10.7 Z',
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
		expect(w.get('[data-testid="profile-card"] svg g g').attributes('transform')).toBe(
			'translate(45, 0) rotate(90) translate(20, 22.5) scale(-1, 1) translate(-20, -22.5)',
		)

		// Switch to Tab 4: Fenestration Glass (List View) + unified Bead & Gasket Config toolbar button
		await router.push('/series-studio?tab=glass')
		await flushPromises()
		expect(router.currentRoute.value.query.tab).toBe('glass')
		expect(w.findAll('[data-testid="glass-row"]')).toHaveLength(1)
		expect(w.text()).toContain('5mm Clear Float Glass')
		expect(w.text()).toContain('5 mm')
		expect(w.find('[data-testid="global-glazing-config-btn"]').exists()).toBe(true)

		// Switch to Tab 5: Fenestration Hardware (Card View)
		await router.push('/series-studio?tab=hardware')
		await flushPromises()
		expect(router.currentRoute.value.query.tab).toBe('hardware')
		expect(w.findAll('[data-testid="hardware-card"]')).toHaveLength(1)
		expect(w.text()).toContain('G22 · Glazing Gasket 2mm')
		expect(w.find('[data-testid="add-hardware-card"]').exists()).toBe(true)
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

		// Profile Type is visible for frame profiles and automatically hidden for bead/gasket roles
		expect(w.find('[data-testid="profile-type-field"]').exists()).toBe(true)
		const roleControl = w.findAllComponents({ name: 'FormControl' }).find((c) => c.props('label') === 'Role *')
		expect(roleControl).toBeTruthy()
		roleControl!.vm.$emit('update:modelValue', 'bead')
		await flushPromises()
		expect(w.find('[data-testid="profile-type-field"]').exists()).toBe(false)
		roleControl!.vm.$emit('update:modelValue', 'gasket')
		await flushPromises()
		expect(w.find('[data-testid="profile-type-field"]').exists()).toBe(false)
		roleControl!.vm.$emit('update:modelValue', 'sash')
		await flushPromises()
		expect(w.find('[data-testid="profile-type-field"]').exists()).toBe(true)
	})

	it('creates a new profile, new glass, and new series version', async () => {
		const { saveFenestrationProfile, saveFenestrationGlass, createSeriesVersion } = await import('@/studio/api')
		;(saveFenestrationProfile as ReturnType<typeof vi.fn>).mockResolvedValue({
			name: 'P-NEW',
			profile_code: 'P-NEW',
			profile_name: 'New Frame',
			series: 'CS400',
			role: 'frame',
			bar_lengths: '4880',
			kg_per_m: 1,
		})
		;(saveFenestrationGlass as ReturnType<typeof vi.fn>).mockResolvedValue('G-NEW')
		;(createSeriesVersion as ReturnType<typeof vi.fn>).mockResolvedValue({
			name: 'CS400-V02',
			series: 'CS400',
			version_note: 'v2',
			docstatus: 0,
			deductions: [],
			constants: [],
			member_rules: [],
			hardware_rules: [],
			validation_rules: [],
		})

		const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
		await router.push('/series-studio/profiles/new?series=CS400')
		await router.isReady()
		const wp = mount(ProfileFormPage, { global: { plugins: [router] } })
		await flushPromises()
		const pInputs = wp.findAll('input')
		await pInputs[0].setValue('P-NEW')
		await pInputs[1].setValue('New Frame')
		await wp.get('[data-testid="save-profile-btn"]').trigger('click')
		await flushPromises()
		expect(saveFenestrationProfile).toHaveBeenCalled()

		await router.push('/series-studio/glass/new')
		const wg = mount(GlassFormPage, { global: { plugins: [router] } })
		await flushPromises()
		const gInputs = wg.findAll('input')
		await gInputs[0].setValue('G-NEW')
		await gInputs[1].setValue('New Glass 6mm')
		await wg.get('[data-testid="save-glass-btn"]').trigger('click')
		await flushPromises()
		expect(saveFenestrationGlass).toHaveBeenCalled()

		await router.push('/series-studio/versions/new?series=CS400')
		const wv = mount(SeriesVersionFormPage, { global: { plugins: [router] } })
		await flushPromises()
		await wv.get('[data-testid="save-version-btn"]').trigger('click')
		await flushPromises()
		expect(createSeriesVersion).toHaveBeenCalled()
	})

	it('renders Section Templates Studio with interactive SectionView, auto-glass, and template switching', async () => {
		const { saveSeriesSectionConfig } = await import('@/studio/api')
		const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })
		await router.push('/series-studio/series/CS400/section-config')
		await router.isReady()

		const w = mount(SeriesSectionConfigPage, {
			props: { name: 'CS400' },
			global: { plugins: [router] },
		})
		await flushPromises()

		expect(w.text()).toContain('Section Templates · CS400')
		expect(w.find('[data-testid="section-templates-sidebar"]').exists()).toBe(true)
		expect(w.find('[data-testid="template-item-fixed_window"]').exists()).toBe(true)
		expect(w.find('[data-testid="template-item-fixed_door"]').exists()).toBe(true)
		expect(w.find('[data-testid="template-item-fixed_window_mullion"]').exists()).toBe(true)
		expect(w.find('[data-testid="template-item-openable_window"]').exists()).toBe(true)
		expect(w.find('[data-testid="template-item-openable_door_mullion"]').exists()).toBe(true)
		expect(w.find('[data-testid="template-item-sliding_window"]').exists()).toBe(true)

		// Auto-resolved Bead & Gasket pill comes directly from Fenestration Glass rules
		expect(w.get('[data-testid="resolved-glass-rule-pill"]').text()).toContain('Bead: CS4807-CS400')

		// Embedded interactive SectionView canvas renders with auto-glass (glass marked stationary)
		expect(w.find('[data-testid="template-section-canvas"]').exists()).toBe(true)
		const glassEl = w.find('[data-kind="glass"]')
		expect(glassEl.exists()).toBe(true)
		expect(glassEl.attributes('data-stationary')).toBe('true')

		// Switch to Openable Door and verify Door profiles are auto-selected in Template Profiles
		await w.get('[data-testid="template-item-openable_door"]').trigger('click')
		await flushPromises()
		expect(w.get('[data-testid="override-profile-frame"]').text()).toContain('Auto (CS4805)')
		expect(w.get('[data-testid="override-profile-sash"]').text()).toContain('Auto (CS4804)')

		// Switch to Openable Window + Mullion, set Glass Domain, and save template
		await w.get('[data-testid="template-item-openable_window_mullion"]').trigger('click')
		await flushPromises()
		expect(w.text()).toContain('Openable Window + Mullion')
		expect(w.get('[data-testid="axis-sync-pill"]').text()).toContain('B–B ↔ A–A Auto-Sync')
		expect(w.get('[data-testid="override-profile-frame"]').text()).toContain('Auto (E104156)')

		// Initialize Glass Domain and verify red hatched domain overlay + align controls appear
		await w.get('[data-testid="init-glass-domain-btn"]').trigger('click')
		await flushPromises()
		expect(w.find('[data-testid="glass-domain-overlay"]').exists()).toBe(true)
		await w.get('[data-testid="domain-align-top"]').trigger('click')
		await flushPromises()

		await w.get('[data-testid="save-section-config-btn"]').trigger('click')
		await flushPromises()
		expect(saveSeriesSectionConfig).toHaveBeenCalledWith(
			'CS400',
			expect.objectContaining({
				version: 1,
				templates: expect.objectContaining({
					openable_window_mullion: expect.objectContaining({
						configured: true,
						axis_h: expect.objectContaining({
							glassDomain: expect.objectContaining({
								configured: true,
								align: 'top',
							}),
						}),
						axis_v: expect.objectContaining({
							glassDomain: expect.objectContaining({
								configured: true,
								align: 'top',
							}),
						}),
					}),
				}),
			}),
		)
	})

	it('keeps GlassFormPage clean and renders redesigned global GlazingConfigPage and HardwareFormPage', async () => {
		const { saveGlobalGlazingRules, saveFenestrationHardware } = await import('@/studio/api')
		const router = createRouter({ history: createMemoryHistory('/fenestration'), routes })

		await router.push('/series-studio/profiles/LP101-CS400')
		await router.isReady()
		const wp = mount(ProfileFormPage, { props: { name: 'LP101-CS400' }, global: { plugins: [router] } })
		await flushPromises()
		expect(wp.find('[data-testid="profile-anchors-toolbar"]').exists()).toBe(false)

		await router.push('/series-studio/glass/new')
		const wg = mount(GlassFormPage, { global: { plugins: [router] } })
		await flushPromises()
		expect(wg.find('[data-testid="glass-glazing-rules-section"]').exists()).toBe(false)

		await router.push('/series-studio/glazing-config')
		const wgc = mount(GlazingConfigPage, { global: { plugins: [router] } })
		await flushPromises()
		expect(wgc.text()).toContain('Bead & Gasket Configuration')
		// Shared rule appears in both Window and Door accordions
		const winAcc = wgc.get('[data-testid="accordion-window"]')
		const doorAcc = wgc.get('[data-testid="accordion-door"]')
		expect(winAcc.findAll('[data-testid="global-glazing-rule-card"]')).toHaveLength(1)
		expect(doorAcc.findAll('[data-testid="global-glazing-rule-card"]')).toHaveLength(1)

		// Add a Window-only rule with None (No Beading) for Sash
		await wgc.get('[data-testid="add-window-rule-btn"]').trigger('click')
		await flushPromises()
		expect(winAcc.findAll('[data-testid="global-glazing-rule-card"]')).toHaveLength(2)
		expect(doorAcc.findAll('[data-testid="global-glazing-rule-card"]')).toHaveLength(1)
		await wgc.get('[data-testid="rule-bead-profile-select"]').setValue('')
		await wgc.get('[data-testid="rule-host-select"]').setValue('sash')
		await flushPromises()
		// Add an Auto BW channel (12.01 mm) and verify Live Resolution Preview resolves 5mm -> G24 (4mm outer) + G23 (3mm inner)
		expect(wgc.find('[data-testid="auto-glazing-section"]').exists()).toBe(true)
		await wgc.get('[data-testid="add-auto-bead-btn"]').trigger('click')
		await flushPromises()
		expect(wgc.findAll('[data-testid="auto-channel-row"]')).toHaveLength(1)
		expect(wgc.find('[data-testid="auto-preview-matrix"]').exists()).toBe(true)
		expect(wgc.get('[data-testid="auto-preview-matrix"]').text()).toContain('G24')
		expect(wgc.get('[data-testid="auto-preview-matrix"]').text()).toContain('G23')

		await wgc.get('[data-testid="save-global-glazing-btn"]').trigger('click')
		await flushPromises()
		expect(saveGlobalGlazingRules).toHaveBeenCalledWith(
			expect.arrayContaining([
				expect.objectContaining({
					profile_type: 'window',
					host: 'sash',
					bead_profile: '',
					no_bead: true,
				}),
			]),
			expect.objectContaining({
				enabled: true,
				thicker_gasket_side: 'outer',
				max_compression_mm: 1,
				channels: expect.arrayContaining([
					expect.objectContaining({
						series: 'CS400',
						bead_width_mm: 12.01,
					}),
				]),
			}),
		)

		await router.push('/series-studio/hardware/new')
		const wh = mount(HardwareFormPage, { global: { plugins: [router] } })
		await flushPromises()
		expect(wh.find('[data-testid="hardware-dxf-dropzone"]').exists()).toBe(true)
		const hInputs = wh.findAll('input')
		await hInputs[0].setValue('G23')
		await hInputs[1].setValue('Glazing Gasket 3mm')
		await wh.get('[data-testid="save-hardware-btn"]').trigger('click')
		await flushPromises()
		expect(saveFenestrationHardware).toHaveBeenCalled()
	})
})

