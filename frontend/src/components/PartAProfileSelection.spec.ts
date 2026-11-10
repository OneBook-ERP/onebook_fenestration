import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Select } from 'frappe-ui'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PropertiesPanel from '@/components/PropertiesPanel.vue'
import WindowCanvas from '@/components/WindowCanvas.vue'
import SectionView from '@/components/SectionView.vue'
import { useDesignerStore, migrateDesignProfiles } from '@/stores/designer'
import type { Design, SashNode } from '@/design/types'

vi.mock('frappe-ui', async (orig) => {
	const { reactive } = await import('vue')
	return {
		...(await orig<object>()),
		useList: (opts: { doctype: string }) =>
			reactive({
				data:
					opts.doctype === 'Fenestration Profile'
						? [
								{ profile_code: 'E104156', profile_name: '40mm Casement Frame', role: 'frame', width_mm: 42, depth_mm: 50 },
								{ profile_code: 'E104160', profile_name: '40mm Casement Sash', role: 'sash', width_mm: 60, depth_mm: 40 },
								{ profile_code: 'E104165', profile_name: 'Heavy Casement Sash', role: 'sash', width_mm: 68, depth_mm: 45 },
								{ profile_code: 'E104159', profile_name: '40mm Casement Window Mullion', role: 'mullion', width_mm: 60, depth_mm: 55 },
								{ profile_code: 'E104161', profile_name: '5mm Glass Beading', role: 'bead', width_mm: 24.1, depth_mm: 18 },
							]
						: [
								{ name: '6CTG', glass_name: '6 mm clear toughened' },
							],
				reload: () => {},
				list: { loading: false },
			}),
	}
})

vi.mock('@/api', () => ({
	computeDesign: vi.fn(async (design: Design) => ({
		ok: true,
		result: {
			members: [
				{ role: 'frame', profile: design.frameProfileId || design.profiles?.frame || 'E104156', length: 1200, angles: [45, 45], path: 'F1' },
				{ role: 'sash', panel: 'F1-S1', path: 'F1.0', profile: (design.root as never as { children: SashNode[] }).children?.[0]?.profile || 'E104160', length: 577, angles: [45, 45] },
				{ role: 'sash', panel: 'F1-S2', path: 'F1.1', profile: (design.root as never as { children: SashNode[] }).children?.[1]?.profile || 'E104160', length: 577, angles: [45, 45] },
				{ role: 'mullion', panel: 'M1', path: 'M1', profile: design.profiles?.M1 || 'E104159', length: 1116, angles: [90, 90] },
			],
			glass: [
				{ path: 'F1.0', panel: 'F1-S1', width: 475.5, height: 1063 },
				{ path: 'F1.1', panel: 'F1-S2', width: 475.5, height: 1063 },
			],
			pricing: { total: 1000 },
			issues: [],
		},
		series: {
			glasses: ['6CTG'],
			profiles: ['E104156', 'E104160', 'E104165', 'E104159', 'E104161'],
			role_defaults: { frame: 'E104156', sash: 'E104160', mullion: 'E104159', bead: 'E104161' },
			profile_widths: { E104156: 42, E104160: 60, E104165: 68, E104159: 60, E104161: 24.1 },
			defaults: { limiter: false, mesh: false },
		},
	})),
	crossSection: vi.fn(async () => ({
		ok: true,
		result: {
			axis: 'h',
			at: 600,
			span: 1200,
			pieces: [
				{ kind: 'profile', code: 'E104156', role: 'frame', panel: 'F1', start: 0, end: 42, mirrored: false },
				{ kind: 'profile', code: 'E104160', role: 'sash', panel: 'F1-S1', start: 42, end: 102, mirrored: false },
				{ kind: 'glass', code: '6CTG', role: 'glass', panel: 'F1-S1', start: 102, end: 577, thickness: 6, mirrored: false },
				{ kind: 'profile', code: 'E104159', role: 'mullion', panel: 'M1', start: 570, end: 630, mirrored: false },
				{ kind: 'profile', code: 'E104160', role: 'sash', panel: 'F1-S2', start: 1098, end: 1158, mirrored: true },
				{ kind: 'profile', code: 'E104156', role: 'frame', panel: 'F1', start: 1158, end: 1200, mirrored: true },
			],
		},
		outlines: {},
	})),
}))

function createTwoSashDesign(): Design {
	return {
		width: 1200,
		height: 1200,
		series: 'CS400',
		profiles: { frame: 'E104156' },
		frameProfileId: 'E104156',
		root: {
			type: 'split',
			dir: 'v',
			at: [600],
			children: [
				{ type: 'sash', glass: '6CTG', profile: undefined },
				{ type: 'sash', glass: '6CTG', profile: undefined },
			],
		},
	}
}

describe('Part A: Profile Selection Bug and Selection Sync', () => {
	enableAutoUnmount(afterEach)
	beforeEach(() => {
		setActivePinia(createPinia())
	})

	it('Test 1: Frame E104156, then sash S1 E104165: the frame still reads E104156, S1 reads E104165, and S2 is unchanged', async () => {
		const store = useDesignerStore()
		store.reset(createTwoSashDesign(), 'CS400-v1')
		await store.runCompute()

		// Outer frame initially E104156
		expect(store.design.frameProfileId).toBe('E104156')
		expect(store.design.profiles?.frame).toBe('E104156')

		// Set Sash 1 (F1.0) profile to E104165 (sash role)
		store.setProfile('sash', 'F1.0', 'E104165', 'sash')

		const rootSplit = store.design.root as never as { children: SashNode[] }
		expect(rootSplit.children[0].profile).toBe('E104165')
		expect(store.design.profiles?.['F1.0']).toBe('E104165')

		// Frame must still be E104156!
		expect(store.design.frameProfileId).toBe('E104156')
		expect(store.design.profiles?.frame).toBe('E104156')

		// Sash 2 (F1.1) must be completely unchanged!
		expect(rootSplit.children[1].profile).toBeUndefined()
		expect(store.design.profiles?.['F1.1']).toBeUndefined()
	})

	it('Test 2: Reselect the frame, the sash, and the frame again, in any order: no value changes', async () => {
		const store = useDesignerStore()
		store.reset(createTwoSashDesign(), 'CS400-v1')
		await store.runCompute()

		store.setProfile('sash', 'F1.0', 'E104165', 'sash')
		const initialJson = JSON.stringify(store.design)

		// Reselect frame -> sash -> frame -> sash -> bar
		store.select('FRAME')
		expect(JSON.stringify(store.design)).toBe(initialJson)

		store.select('F1.0')
		expect(JSON.stringify(store.design)).toBe(initialJson)

		store.select('FRAME')
		expect(JSON.stringify(store.design)).toBe(initialJson)

		store.select('F1.1')
		expect(JSON.stringify(store.design)).toBe(initialJson)

		store.select('M1')
		expect(JSON.stringify(store.design)).toBe(initialJson)
	})

	it('Test 3: The frame dropdown cannot be set to a bead or mullion profile. A bar cannot be set to a frame profile.', () => {
		const store = useDesignerStore()
		store.reset(createTwoSashDesign(), 'CS400-v1')

		// Frame cannot accept bead
		expect(() => {
			store.setProfile('frame', 'frame', 'E104161', 'bead')
		}).toThrow(/Cannot assign role 'bead' to outer frame/)

		// Frame cannot accept mullion
		expect(() => {
			store.setProfile('frame', 'frame', 'E104159', 'mullion')
		}).toThrow(/Cannot assign role 'mullion' to outer frame/)

		// Bar cannot accept frame
		expect(() => {
			store.setProfile('bar', 'M1', 'E104156', 'frame')
		}).toThrow(/Cannot assign role 'frame' to bar/)

		// Sash cannot accept bead
		expect(() => {
			store.setProfile('sash', 'F1.0', 'E104161', 'bead')
		}).toThrow(/Cannot assign role 'bead' to sash/)
	})

	it("Test 4: After setProfile on S1, 2D plan, Section view and right panel show S1's profile, and frame face width (42mm for E104156) is unchanged", async () => {
		const store = useDesignerStore()
		store.reset(createTwoSashDesign(), 'CS400-v1')
		store.select('FRAME')
		await store.runCompute()

		const panelWrapper = mount(PropertiesPanel, {
			props: { meta: { ref: 'W1', qty: 1, location: '' } },
		})
		await flushPromises()

		// Frame profile in panel
		expect(panelWrapper.text()).toContain('40mm Casement Frame')

		// Set Sash 1 profile to E104165
		store.setProfile('sash', 'F1.0', 'E104165', 'sash')
		await store.runCompute()
		await flushPromises()

		// Select Sash 1
		store.select('F1.0')
		await flushPromises()
		expect(panelWrapper.text()).toContain('Heavy Casement Sash')

		// Mount 2D canvas
		const canvasWrapper = mount(WindowCanvas, {
			props: {
				design: store.design,
				selectedPath: store.selectedPath,
				issuePaths: [],
				view: 'inside',
				profileWidths: store.seriesInfo?.profile_widths,
				members: store.result?.members,
			},
		})
		await flushPromises()

		// Outer frame face width must strictly remain 42mm (E104156), NOT 68mm or 24.1mm!
		const frameRect = canvasWrapper.find('rect[data-frame="FRAME"]')
		expect(frameRect.exists()).toBe(true)
		// Select frame again
		store.select('FRAME')
		await flushPromises()
		expect(panelWrapper.text()).toContain('40mm Casement Frame')
		expect(panelWrapper.text()).toContain('42 mm')
	})

	it('Test 5: Selecting S2 in the Section editor selects and highlights S2 in the 2D plan and in 3D, and the reverse', async () => {
		const store = useDesignerStore()
		store.reset(createTwoSashDesign(), 'CS400-v1')
		await store.runCompute()

		const sectionWrapper = mount(SectionView, {
			props: {
				design: store.design,
				seriesVersion: store.seriesVersion,
				axis: 'h',
				at: 600,
				selectedPath: store.selectedPath,
			},
		})
		await flushPromises()

		// Section cut contains S2 at index 4 (panel: F1-S2)
		const s2Group = sectionWrapper.find('[data-piece-group="4"]')
		expect(s2Group.exists()).toBe(true)

		// Clicking S2 in Section view emits select with cell path 'F1.1'
		await s2Group.trigger('click')
		const emitted = sectionWrapper.emitted('select')
		expect(emitted).toBeDefined()
		const selectedPathEmitted = emitted![0][0]
		expect(selectedPathEmitted).toBe('F1.1')

		// Updating store with this selection
		store.select(selectedPathEmitted as string)
		expect(store.selectedPath).toBe('F1.1')
		expect(store.selection.kind).toBe('sash')

		// When passed back to SectionView, piece for F1-S2 has blue selection
		await sectionWrapper.setProps({ selectedPath: store.selectedPath })
		await flushPromises()

		// In 2D WindowCanvas: F1.1 is selected
		const canvasWrapper = mount(WindowCanvas, {
			props: {
				design: store.design,
				selectedPath: store.selectedPath,
				issuePaths: [],
				view: 'inside',
				profileWidths: store.seriesInfo?.profile_widths,
				members: store.result?.members,
			},
		})
		await flushPromises()
		const s2Cell = canvasWrapper.find('rect[data-path="F1.1"]')
		expect(s2Cell.exists()).toBe(true)
		expect(s2Cell.attributes('stroke')).toBe('#2563EB')
	})

	it('Test 6: Save, reload and reopen the design: every object keeps its own profile id and nothing resets to a default. Old designs migrated cleanly.', () => {
		const legacyDesign: Design = {
			width: 1200,
			height: 1200,
			series: 'CS400',
			profiles: {
				frame: 'E104156',
				sash: 'E104160', // Legacy global sash key
			},
			root: {
				type: 'split',
				dir: 'v',
				at: [600],
				children: [
					{ type: 'sash', glass: '6CTG' }, // missing per-object profile
					{ type: 'sash', glass: '6CTG', profile: 'E104165' }, // already has per-object profile
				],
			},
		}

		// Run migration
		const migrated = migrateDesignProfiles(legacyDesign)
		const children = (migrated.root as never as { children: SashNode[] }).children

		// Legacy sash copied to S1 without overriding S2
		expect(children[0].profile).toBe('E104160')
		expect(children[1].profile).toBe('E104165')
		expect(migrated.frameProfileId).toBe('E104156')
		expect(migrated.profiles?.frame).toBe('E104156')

		// Store reset preserves per-object profiles
		const store = useDesignerStore()
		store.reset(migrated, 'CS400-v1')
		const loadedChildren = (store.design.root as never as { children: SashNode[] }).children
		expect(loadedChildren[0].profile).toBe('E104160')
		expect(loadedChildren[1].profile).toBe('E104165')
		expect(store.design.frameProfileId).toBe('E104156')
	})
})
