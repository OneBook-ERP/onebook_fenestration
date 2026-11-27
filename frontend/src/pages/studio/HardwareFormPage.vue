<template>
	<div class="mx-auto max-w-6xl p-6">
		<header class="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-outline-gray-2 pb-4">
			<div>
				<nav aria-label="Breadcrumb" class="mb-1 flex items-center gap-1.5 text-sm text-ink-gray-5">
					<router-link to="/series-studio?tab=hardware" class="hover:text-ink-gray-8">
						Series Studio
					</router-link>
					<span aria-hidden="true">/</span>
					<router-link to="/series-studio?tab=hardware" class="hover:text-ink-gray-8">
						Fenestration Hardware
					</router-link>
					<span aria-hidden="true">/</span>
					<span class="font-medium text-ink-gray-8">{{ isEdit ? form.hardware_code : 'New Hardware' }}</span>
				</nav>
				<div class="flex flex-wrap items-center gap-3">
					<h1 class="text-xl font-semibold text-ink-gray-9">
						{{ isEdit ? `${form.hardware_code} · ${form.hardware_name || 'Hardware'}` : (form.hardware_name || 'New Fenestration Hardware') }}
					</h1>
					<Badge v-if="form.category" theme="blue" :label="form.category" />
					<Badge :theme="hasSvg ? 'green' : 'gray'" :label="hasSvg ? 'DXF Parsed' : 'No DXF'" />
				</div>
			</div>

			<div class="flex items-center gap-2.5">
				<Button variant="outline" label="Back to Hardware" route="/series-studio?tab=hardware" />
				<Button
					variant="solid"
					:label="isEdit ? 'Save Changes' : 'Create Hardware'"
					:loading="saving"
					:disabled="!canSave"
					data-testid="save-hardware-btn"
					@click="save"
				/>
			</div>
		</header>

		<div v-if="loadingDoc" class="py-12 text-center text-sm text-ink-gray-5">
			Loading hardware record…
		</div>

		<div v-else class="space-y-8">
			<Alert v-if="error" theme="red" :title="error" />

			<!-- Section 1: Hardware Configuration -->
			<section>
				<h2 class="mb-4 text-base font-semibold text-ink-gray-9">Hardware Configuration</h2>
				<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
					<div class="space-y-4">
						<FormControl
							v-model="form.hardware_code"
							label="Hardware Code *"
							placeholder="e.g. G22, G23, HDL-01, HNG-40"
							:disabled="isEdit"
						/>
						<FormControl
							v-model="form.hardware_name"
							label="Hardware Name *"
							placeholder="e.g. 2mm Glazing Gasket or Casement Handle"
						/>
						<FormControl
							v-model="form.category"
							type="select"
							label="Category *"
							:options="categoryOptions"
						/>
						<Combobox
							v-model="form.item"
							label="ERPNext Item"
							placeholder="Search or select ERPNext Item..."
							:options="itemOptions"
						/>
						<FormControl
							v-model="form.description"
							type="textarea"
							label="Description / Notes"
							placeholder="Optional fitting notes, compatible groove, or finish details..."
						/>
					</div>

					<div class="space-y-4">
						<div class="grid grid-cols-2 gap-4">
							<FormControl
								v-model="form.uom"
								type="select"
								label="Unit of Measure"
								:options="uomOptions"
							/>
							<FormControl
								v-model.number="form.thickness_mm"
								type="number"
								step="0.5"
								label="Thickness / Gap (mm)"
								placeholder="e.g. 2, 3, 4, 5"
							/>
						</div>

						<FormControl
							v-model.number="form.weight_kg"
							type="number"
							step="0.001"
							label="Weight (kg)"
							placeholder="e.g. 0.045"
						/>

						<!-- Drag & Drop DXF Upload Zone -->
						<div>
							<label class="mb-1.5 block text-xs text-ink-gray-6">CAD / Section DXF (Gaskets, Beadings, Hardware)</label>
							<input
								ref="fileInput"
								type="file"
								accept=".dxf"
								class="hidden"
								data-testid="hardware-dxf-input"
								@change="onFilePick"
							/>
							<div
								data-testid="hardware-dxf-dropzone"
								class="rounded-xl border-2 border-dashed p-5 text-center transition-colors"
								:class="
									isDragging
										? 'border-blue-500 bg-blue-50/40'
										: 'border-outline-gray-3 bg-surface-gray-1/60 hover:border-ink-gray-6'
								"
								@dragover.prevent="isDragging = true"
								@dragleave.prevent="isDragging = false"
								@drop.prevent="onFileDrop"
							>
								<div v-if="uploadingDxf || parsingDxf" class="py-2 text-sm text-ink-gray-7">
									<span class="font-medium">
										{{ uploadingDxf ? `Uploading DXF (${uploadProgress}%)…` : 'Analyzing CAD cross-section geometry…' }}
									</span>
								</div>
								<div v-else-if="form.dxf_file" class="flex flex-wrap items-center justify-between gap-3 text-left">
									<div class="min-w-0 flex-1">
										<div class="truncate text-sm font-semibold text-ink-gray-9">
											{{ cleanDxfFilename(form.dxf_file) }}
										</div>
										<div class="truncate font-mono text-xs text-ink-gray-5">
											{{ form.dxf_file }}
										</div>
									</div>
									<div class="flex items-center gap-2">
										<Button variant="outline" size="sm" label="Replace .dxf" @click="triggerFilePicker" />
										<Button variant="subtle" size="sm" label="Clear" @click="clearDxf" />
									</div>
								</div>
								<div v-else class="cursor-pointer space-y-1.5 py-2" @click="triggerFilePicker">
									<div class="text-sm font-semibold text-ink-gray-8">
										Drag and drop a CAD <code class="rounded bg-surface-gray-2 px-1 py-0.5 text-xs">.dxf</code> file here, or click to browse
									</div>
									<div class="text-xs text-ink-gray-5">
										Supports gaskets (G22–G25), beadings, blocks, and open/closed polylines
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</section>

			<!-- Section 2: CAD Section Blueprint Inspector -->
			<section class="border-t border-outline-gray-2 pt-6">
				<div class="mb-4 flex flex-wrap items-start justify-between gap-4">
					<div>
						<h2 class="text-base font-semibold text-ink-gray-9">
							Section Preview (from DXF)
							<span v-if="form.dxf_file" class="font-normal text-ink-gray-5">
								· {{ cleanDxfFilename(form.dxf_file) }}
							</span>
						</h2>
						<p v-if="hasSvg" class="mt-0.5 text-xs text-ink-gray-5">
							{{ metrics.loops }} closed loop{{ metrics.loops === 1 ? '' : 's' }}
							· {{ formatMetric(form.width_mm, 1) }} × {{ formatMetric(form.depth_mm, 1) }} mm
						</p>
					</div>

					<div v-if="hasSvg" class="flex flex-wrap items-center gap-2">
						<div class="inline-flex items-center overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-gray-1">
							<button
								type="button"
								class="flex h-7 items-center justify-center px-2 text-xs font-semibold text-ink-gray-6 hover:bg-surface-gray-3 hover:text-ink-gray-9"
								title="Rotate Left 90°"
								@click="rotateHardware(-90)"
							>
								↺
							</button>
							<span class="min-w-10 border-x border-outline-gray-2 px-2 py-1 text-center font-mono text-xs font-bold text-blue-600">
								{{ form.section_rotation || '0' }}°
							</span>
							<button
								type="button"
								class="flex h-7 items-center justify-center px-2 text-xs font-semibold text-ink-gray-6 hover:bg-surface-gray-3 hover:text-ink-gray-9"
								title="Rotate Right 90°"
								@click="rotateHardware(90)"
							>
								↻
							</button>
							<button
								type="button"
								class="flex h-7 items-center justify-center border-l border-outline-gray-2 px-2 text-xs font-semibold hover:bg-surface-gray-3"
								:class="form.section_flip_x ? 'bg-blue-50 text-blue-700' : 'text-ink-gray-6'"
								@click="form.section_flip_x = !form.section_flip_x"
							>
								Flip H
							</button>
							<button
								type="button"
								class="flex h-7 items-center justify-center border-l border-outline-gray-2 px-2 text-xs font-semibold hover:bg-surface-gray-3"
								:class="form.section_flip_y ? 'bg-blue-50 text-blue-700' : 'text-ink-gray-6'"
								@click="form.section_flip_y = !form.section_flip_y"
							>
								Flip V
							</button>
						</div>

						<Button
							type="button"
							size="sm"
							variant="subtle"
							:loading="savingOrientation"
							label="Set Default Orientation"
							@click="saveDefaultOrientation"
						/>

						<div class="inline-flex overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-gray-1">
							<button
								type="button"
								class="px-3 py-1 text-xs font-semibold"
								:class="showGrid ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-6'"
								@click="showGrid = !showGrid"
							>
								Grid
							</button>
							<button
								type="button"
								class="border-l border-outline-gray-2 px-3 py-1 text-xs font-semibold"
								:class="showDims ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-6'"
								@click="showDims = !showDims"
							>
								Dimensions
							</button>
							<button
								type="button"
								class="border-l border-outline-gray-2 px-3 py-1 text-xs font-semibold"
								:class="showCentroid ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-6'"
								@click="showCentroid = !showCentroid"
							>
								Centroid
							</button>
						</div>
					</div>
				</div>

				<div
					v-if="hasSvg"
					class="flex min-h-[300px] items-center justify-center overflow-hidden rounded-xl border border-outline-gray-2 bg-slate-50"
				>
					<svg
						data-testid="hardware-blueprint-svg"
						:viewBox="`0 0 ${metrics.cw} ${metrics.ch}`"
						class="block h-[300px] w-full select-none"
						xmlns="http://www.w3.org/2000/svg"
					>
						<defs>
							<pattern
								id="hw-page-grid-min"
								:width="metrics.minorPx"
								:height="metrics.minorPx"
								patternUnits="userSpaceOnUse"
								:patternTransform="`translate(${metrics.ox}, ${metrics.oy})`"
							>
								<path
									:d="`M ${metrics.minorPx} 0 L 0 0 0 ${metrics.minorPx}`"
									fill="none"
									stroke="#e2e8f0"
									stroke-width="0.7"
								/>
							</pattern>
							<pattern
								id="hw-page-grid-maj"
								:width="metrics.majorPx"
								:height="metrics.majorPx"
								patternUnits="userSpaceOnUse"
								:patternTransform="`translate(${metrics.ox}, ${metrics.oy})`"
							>
								<rect :width="metrics.majorPx" :height="metrics.majorPx" fill="url(#hw-page-grid-min)" />
								<path
									:d="`M ${metrics.majorPx} 0 L 0 0 0 ${metrics.majorPx}`"
									fill="none"
									stroke="#cbd5e1"
									stroke-width="1.1"
								/>
							</pattern>
						</defs>

						<rect v-if="showGrid" x="0" y="0" :width="metrics.cw" :height="metrics.ch" fill="url(#hw-page-grid-maj)" />

						<g :transform="`translate(${metrics.ox}, ${metrics.oy}) scale(${metrics.s})`">
							<g :transform="rotationTransform">
								<path
									:d="form.section_svg || ''"
									fill="#94a3b8"
									fill-opacity="0.86"
									stroke="#1e293b"
									:stroke-width="metrics.pathStroke"
									stroke-linejoin="round"
									fill-rule="evenodd"
								/>
							</g>
						</g>

						<g v-if="showDims" stroke="#475569" stroke-width="1.15" stroke-linecap="square">
							<line :x1="metrics.ox" :y1="metrics.dimY" :x2="metrics.ox + metrics.dw" :y2="metrics.dimY" />
							<line :x1="metrics.ox" :y1="metrics.dimY - metrics.tick" :x2="metrics.ox" :y2="metrics.dimY + metrics.tick" />
							<line :x1="metrics.ox + metrics.dw" :y1="metrics.dimY - metrics.tick" :x2="metrics.ox + metrics.dw" :y2="metrics.dimY + metrics.tick" />

							<line :x1="metrics.dimX" :y1="metrics.oy" :x2="metrics.dimX" :y2="metrics.oy + metrics.dh" />
							<line :x1="metrics.dimX - metrics.tick" :y1="metrics.oy" :x2="metrics.dimX + metrics.tick" :y2="metrics.oy" />
							<line :x1="metrics.dimX - metrics.tick" :y1="metrics.oy + metrics.dh" :x2="metrics.dimX + metrics.tick" :y2="metrics.oy + metrics.dh" />
						</g>
						<template v-if="showDims">
							<text
								:x="metrics.ox + metrics.dw / 2"
								:y="metrics.dimY + 18"
								text-anchor="middle"
								fill="#0f172a"
								:font-size="metrics.fontSize"
								font-weight="600"
							>
								{{ metrics.widthLabel }}
							</text>
							<text
								:x="metrics.vTextX"
								:y="metrics.vTextY"
								text-anchor="middle"
								dominant-baseline="central"
								fill="#0f172a"
								:font-size="metrics.fontSize"
								font-weight="600"
								:transform="`rotate(-90 ${metrics.vTextX} ${metrics.vTextY})`"
							>
								{{ metrics.depthLabel }}
							</text>
						</template>

						<g v-if="showCentroid">
							<circle :cx="metrics.cx" :cy="metrics.cy" r="3.4" fill="#2563eb" stroke="#ffffff" stroke-width="1.2" />
						</g>
					</svg>
				</div>
				<div
					v-else
					class="rounded-xl border border-outline-gray-2 bg-slate-50 p-8 text-center text-ink-gray-5"
				>
					<div class="text-sm font-semibold text-ink-gray-8">No DXF Attached</div>
					<div class="mt-1 text-xs">
						Upload a <code>.dxf</code> file above to preview the hardware / gasket cross-section geometry.
					</div>
				</div>

				<div
					v-if="hasSvg"
					class="mt-3 grid grid-cols-1 gap-px overflow-hidden rounded-xl border border-outline-gray-2 bg-outline-gray-2 sm:grid-cols-3"
				>
					<div class="bg-surface-white p-3.5">
						<div class="text-[11px] font-semibold uppercase tracking-wider text-ink-gray-5">Dimensions</div>
						<div class="mt-1 text-sm font-bold text-ink-gray-9">
							{{ formatMetric(form.width_mm, 1) }} × {{ formatMetric(form.depth_mm, 1) }}
							<span class="text-xs font-medium text-ink-gray-5">mm</span>
						</div>
					</div>
					<div class="bg-surface-white p-3.5">
						<div class="text-[11px] font-semibold uppercase tracking-wider text-ink-gray-5">Section Area</div>
						<div class="mt-1 text-sm font-bold text-ink-gray-9">
							{{ formatMetric(form.area_mm2, 1) }}
							<span class="text-xs font-medium text-ink-gray-5">mm²</span>
						</div>
					</div>
					<div class="bg-surface-white p-3.5">
						<div class="text-[11px] font-semibold uppercase tracking-wider text-ink-gray-5">Perimeter</div>
						<div class="mt-1 text-sm font-bold text-ink-gray-9">
							{{ formatMetric(form.perimeter_mm, 1) }}
							<span class="text-xs font-medium text-ink-gray-5">mm</span>
						</div>
					</div>
				</div>
			</section>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Alert, Badge, Button, Combobox, FormControl, toast, upload, useList } from 'frappe-ui'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
	getFenestrationHardwareDoc,
	HARDWARE_CATEGORIES,
	previewDxf,
	saveFenestrationHardware,
	setHardwareOrientation,
	type FenestrationHardwareRow,
} from '@/studio/api'
import { cleanDxfFilename, computeBlueprintSvgMetrics, profileRotationTransform } from '@/studio/sectionSvg'

const props = defineProps<{ name?: string }>()
const router = useRouter()

const isEdit = computed(() => Boolean(props.name))
const loadingDoc = ref(false)
const saving = ref(false)
const savingOrientation = ref(false)
const error = ref('')

const showGrid = ref(true)
const showDims = ref(true)
const showCentroid = ref(true)
const isDragging = ref(false)
const uploadingDxf = ref(false)
const uploadProgress = ref(0)
const parsingDxf = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const form = reactive({
	name: '',
	hardware_code: '',
	hardware_name: '',
	category: 'Gasket',
	item: '',
	uom: 'Meter',
	thickness_mm: null as number | null,
	weight_kg: null as number | null,
	description: '',
	dxf_file: '',
	section_svg: '',
	width_mm: null as number | null,
	depth_mm: null as number | null,
	raw_width_mm: null as number | null,
	raw_depth_mm: null as number | null,
	area_mm2: null as number | null,
	perimeter_mm: null as number | null,
	section_rotation: '0',
	section_flip_x: false,
	section_flip_y: false,
	section_warnings: '',
})

const categoryOptions = HARDWARE_CATEGORIES.map((c) => ({ label: c, value: c }))
const uomOptions = ['Meter', 'Nos', 'Set', 'Pair', 'Kg'].map((u) => ({ label: u, value: u }))

const itemsResource = useList<{ name: string; item_name?: string; fen_item_kind?: string }>({
	doctype: 'Item',
	fields: ['name', 'item_name', 'fen_item_kind'],
	limit: 500,
})

const itemOptions = computed(() =>
	(itemsResource.data ?? []).map((i) => ({
		label: i.item_name ? `${i.name} — ${i.item_name}` : i.name,
		value: i.name,
	})),
)

const hasSvg = computed(() => Boolean(form.section_svg && form.width_mm && form.depth_mm))
const metrics = computed(() => computeBlueprintSvgMetrics(form, showDims.value))

const rotationTransform = computed(() =>
	profileRotationTransform({
		section_rotation: form.section_rotation,
		section_flip_x: form.section_flip_x,
		section_flip_y: form.section_flip_y,
		width_mm: form.width_mm,
		depth_mm: form.depth_mm,
	}),
)

const canSave = computed(() =>
	Boolean(
		String(form.hardware_code ?? '').trim() &&
			String(form.hardware_name ?? '').trim() &&
			form.category &&
			!saving.value &&
			!uploadingDxf.value &&
			!parsingDxf.value,
	),
)

function formatMetric(val: number | null | undefined, dp: number): string {
	if (val == null || Number.isNaN(Number(val))) return '—'
	return Number(val).toFixed(dp)
}

function rotateHardware(deltaDeg: number) {
	const cur = Number(form.section_rotation || 0)
	const next = (((cur + deltaDeg) % 360) + 360) % 360
	form.section_rotation = String(next)
	if (form.raw_width_mm != null && form.raw_depth_mm != null) {
		const isTurned = next === 90 || next === 270
		form.width_mm = isTurned ? form.raw_depth_mm : form.raw_width_mm
		form.depth_mm = isTurned ? form.raw_width_mm : form.raw_depth_mm
	}
}

async function saveDefaultOrientation() {
	if (!props.name) {
		toast.success(`Orientation set to ${form.section_rotation || '0'}° (will save with hardware)`)
		return
	}
	savingOrientation.value = true
	try {
		const res = await setHardwareOrientation(props.name, {
			rotation: form.section_rotation,
			flip_x: form.section_flip_x,
			flip_y: form.section_flip_y,
		})
		form.section_rotation = String(res.section_rotation)
		form.section_flip_x = Boolean(res.section_flip_x)
		form.section_flip_y = Boolean(res.section_flip_y)
		form.width_mm = res.width_mm
		form.depth_mm = res.depth_mm
		toast.success(`Default orientation set to ${res.section_rotation}°`)
	} catch (e) {
		toast.error(e instanceof Error ? e.message : 'Could not update orientation')
	} finally {
		savingOrientation.value = false
	}
}

function triggerFilePicker() {
	fileInput.value?.click()
}

async function onFilePick(e: Event) {
	const input = e.target as HTMLInputElement
	const file = input.files?.[0]
	input.value = ''
	if (file) await handleDxfFile(file)
}

async function onFileDrop(e: DragEvent) {
	isDragging.value = false
	const file = e.dataTransfer?.files?.[0]
	if (file) await handleDxfFile(file)
}

async function handleDxfFile(file: File) {
	if (!file.name.toLowerCase().endsWith('.dxf')) {
		error.value = 'Please select a valid .dxf CAD file.'
		return
	}
	error.value = ''
	uploadingDxf.value = true
	uploadProgress.value = 0
	try {
		const uploaded = await upload(file, {
			private: false,
			onProgress: (p) => {
				uploadProgress.value = p.percent
			},
		})
		form.dxf_file = uploaded.file_url
		uploadingDxf.value = false
		parsingDxf.value = true
		const res = await previewDxf(uploaded.file_url)
		if (res.ok) {
			form.area_mm2 = res.section.area_mm2
			form.width_mm = res.section.width_mm
			form.depth_mm = res.section.depth_mm
			form.raw_width_mm = res.section.width_mm
			form.raw_depth_mm = res.section.depth_mm
			form.perimeter_mm = res.section.perimeter_mm
			form.section_svg = res.section.section_svg
			form.section_warnings = res.section.section_warnings
			form.section_rotation = '0'
			form.section_flip_x = false
			form.section_flip_y = false
		} else {
			error.value = res.message
		}
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'DXF upload failed'
	} finally {
		uploadingDxf.value = false
		parsingDxf.value = false
	}
}

function clearDxf() {
	form.dxf_file = ''
	form.section_svg = ''
	form.width_mm = null
	form.depth_mm = null
	form.raw_width_mm = null
	form.raw_depth_mm = null
	form.area_mm2 = null
	form.perimeter_mm = null
	form.section_rotation = '0'
	form.section_flip_x = false
	form.section_flip_y = false
	form.section_warnings = ''
}

function applyDoc(doc: FenestrationHardwareRow) {
	form.name = doc.name
	form.hardware_code = doc.hardware_code || doc.name
	form.hardware_name = doc.hardware_name || ''
	form.category = doc.category || 'Gasket'
	form.item = doc.item || ''
	form.uom = doc.uom || 'Meter'
	form.thickness_mm = doc.thickness_mm ?? null
	form.weight_kg = doc.weight_kg ?? null
	form.description = doc.description || ''
	form.dxf_file = doc.dxf_file || ''
	form.section_svg = doc.section_svg || ''
	form.section_rotation = String(doc.section_rotation || '0')
	form.section_flip_x = Boolean(Number(doc.section_flip_x || 0))
	form.section_flip_y = Boolean(Number(doc.section_flip_y || 0))
	const rot = (((Number(form.section_rotation || 0) % 360) + 360) % 360)
	const isTurned = rot === 90 || rot === 270
	form.raw_width_mm = isTurned ? (doc.depth_mm ?? null) : (doc.width_mm ?? null)
	form.raw_depth_mm = isTurned ? (doc.width_mm ?? null) : (doc.depth_mm ?? null)
	form.width_mm = doc.width_mm ?? null
	form.depth_mm = doc.depth_mm ?? null
	form.area_mm2 = doc.area_mm2 ?? null
	form.perimeter_mm = doc.perimeter_mm ?? null
	form.section_warnings = doc.section_warnings || ''
}

onMounted(async () => {
	if (!props.name) return
	loadingDoc.value = true
	try {
		const doc = await getFenestrationHardwareDoc(props.name)
		applyDoc(doc)
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Could not load hardware record'
	} finally {
		loadingDoc.value = false
	}
})

async function save() {
	if (!canSave.value) return
	saving.value = true
	error.value = ''
	try {
		const saved = await saveFenestrationHardware(
			{
				hardware_code: String(form.hardware_code ?? '').trim(),
				hardware_name: String(form.hardware_name ?? '').trim(),
				category: form.category,
				item: String(form.item ?? '').trim() || null,
				uom: form.uom || 'Meter',
				thickness_mm: form.thickness_mm,
				weight_kg: form.weight_kg,
				description: String(form.description ?? '').trim() || null,
				dxf_file: form.dxf_file || null,
				section_rotation: form.section_rotation || '0',
				section_flip_x: form.section_flip_x ? 1 : 0,
				section_flip_y: form.section_flip_y ? 1 : 0,
			},
			props.name || null,
		)
		applyDoc(saved)
		toast.success(isEdit.value ? 'Hardware updated' : 'Hardware created')
		if (!isEdit.value) {
			router.replace(`/series-studio/hardware/${encodeURIComponent(saved.name)}`)
		}
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Could not save hardware record'
	} finally {
		saving.value = false
	}
}
</script>

