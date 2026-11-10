<template>
	<div class="mx-auto max-w-6xl p-6">
		<header class="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-outline-gray-2 pb-4">
			<div>
				<nav aria-label="Breadcrumb" class="mb-1 flex items-center gap-1.5 text-sm text-ink-gray-5">
					<router-link to="/series-studio?tab=profiles" class="hover:text-ink-gray-8">
						Series Studio
					</router-link>
					<span aria-hidden="true">/</span>
					<router-link
						:to="form.series ? `/series-studio?tab=profiles&series=${form.series}` : '/series-studio?tab=profiles'"
						class="hover:text-ink-gray-8"
					>
						Fenestration Profile
					</router-link>
					<span aria-hidden="true">/</span>
					<span class="font-medium text-ink-gray-8">{{ isEdit ? form.profile_code : 'New Fenestration Profile' }}</span>
				</nav>
				<div class="flex flex-wrap items-center gap-3">
					<h1 class="text-xl font-semibold text-ink-gray-9">
						{{ isEdit ? `${form.profile_code} · ${form.profile_name || 'Profile'}` : (form.profile_name || 'New Fenestration Profile') }}
					</h1>
					<Badge :theme="hasSvg ? 'green' : 'gray'" :label="hasSvg ? 'DXF Parsed' : 'No DXF'" />
					<Badge v-if="form.role" theme="blue" :label="form.role" />
				</div>
			</div>

			<div class="flex items-center gap-2.5">
				<Button
					variant="outline"
					label="Back to Profiles"
					@click="goBack"
				/>
				<Button
					variant="solid"
					:label="isEdit ? 'Save Changes' : 'Create Profile'"
					:loading="saving"
					:disabled="!canSave"
					data-testid="save-profile-btn"
					@click="save"
				/>
			</div>
		</header>

		<div v-if="loadingDoc" class="py-12 text-center text-sm text-ink-gray-5">
			Loading fenestration profile…
		</div>

		<div v-else class="space-y-8">
			<Alert v-if="error" theme="red" :title="error" />

			<!-- Section 1: Profile Configuration -->
			<section>
				<h2 class="mb-4 text-base font-semibold text-ink-gray-9">Profile Configuration</h2>

				<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
					<!-- Left Column -->
					<div class="space-y-4">
						<FormControl
							v-model="form.profile_code"
							label="Profile Code *"
							placeholder="e.g. E104158 or LP101-CS400"
							:disabled="isEdit"
						/>
						<FormControl
							v-model="form.profile_name"
							label="Profile Name *"
							placeholder="e.g. 40mm Casement Frame"
						/>
						<FormControl
							v-model="form.series"
							type="select"
							label="Series *"
							:options="seriesOptions"
						/>
						<FormControl
							v-model="form.role"
							type="select"
							label="Role *"
							:options="roleOptions"
						/>
						<Combobox
							v-model="form.item"
							label="ERPNext Item"
							placeholder="Search or select ERPNext Item..."
							:options="itemOptions"
						/>
					</div>

					<!-- Right Column -->
					<div class="space-y-4">
						<div>
							<FormControl
								v-model="form.bar_lengths"
								label="Bar Lengths (mm) *"
								placeholder="4880, 5800"
							/>
							<p class="mt-1 text-xs text-ink-gray-5">
								Comma-separated stock lengths in mm, e.g. 4880, 5800
							</p>
						</div>

						<div>
							<div class="mb-1.5 flex items-center justify-between">
								<label class="text-xs text-ink-gray-6">Weight (kg/m) *</label>
								<button
									v-if="form.computed_kg_per_m"
									type="button"
									class="text-xs font-medium text-blue-600 hover:text-blue-700 hover:underline"
									title="Copy computed weight into Weight (kg/m)"
									@click="form.kg_per_m = Number(form.computed_kg_per_m)"
								>
									Copy computed ({{ Number(form.computed_kg_per_m).toFixed(3) }} kg/m)
								</button>
							</div>
							<FormControl
								v-model.number="form.kg_per_m"
								type="number"
								step="0.001"
								placeholder="0.785"
							/>
						</div>

						<!-- Drag & Drop DXF Upload Zone -->
						<div>
							<label class="mb-1.5 block text-xs text-ink-gray-6">Section DXF</label>
							<input
								ref="fileInput"
								type="file"
								accept=".dxf"
								class="hidden"
								data-testid="dxf-file-input"
								@change="onFilePick"
							/>
							<div
								data-testid="dxf-dropzone"
								class="rounded-xl border-2 border-dashed p-5 text-center transition-colors"
								:class="
									isDragging
										? 'border-ink-gray-9 bg-surface-gray-2'
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
										Automatically computes section area, bounding dimensions,Ix/Iy, weight (kg/m), and SVG preview
									</div>
								</div>
							</div>
						</div>

						<div class="pt-1">
							<Checkbox
								v-model="form.use_computed_weight"
								label="Use Computed Weight from DXF"
							/>
							<p v-if="form.use_computed_weight && form.computed_kg_per_m" class="mt-1 text-xs text-ink-gray-6">
								Engine will use computed weight: <strong>{{ Number(form.computed_kg_per_m).toFixed(3) }} kg/m</strong>
							</p>
						</div>
					</div>
				</div>
			</section>

			<!-- Section 2: Section (from DXF) Blueprint Inspector -->
			<section class="border-t border-outline-gray-2 pt-6">
				<div class="mb-4 flex flex-wrap items-start justify-between gap-4">
					<div>
						<h2 class="text-base font-semibold text-ink-gray-9">
							Section (from DXF)
							<span v-if="form.dxf_file" class="font-normal text-ink-gray-5">
								· {{ cleanDxfFilename(form.dxf_file) }}
							</span>
						</h2>
						<p v-if="hasSvg" class="mt-0.5 text-xs text-ink-gray-5">
							{{ unitNote }} · {{ metrics.loops }} closed loop{{ metrics.loops === 1 ? '' : 's' }}
							<template v-if="metrics.chambers > 0">
								({{ metrics.chambers }} chamber{{ metrics.chambers === 1 ? '' : 's' }})
							</template>
							· Role: <strong class="capitalize text-ink-gray-8">{{ form.role || '—' }}</strong>
						</p>
					</div>

					<div v-if="hasSvg" class="flex flex-wrap items-center gap-2">
						<!-- Profile Orientation Toolbar -->
						<div class="inline-flex items-center overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-gray-1">
							<button
								type="button"
								class="flex h-7 items-center justify-center px-2 text-xs font-semibold text-ink-gray-6 transition-colors hover:bg-surface-gray-3 hover:text-ink-gray-9"
								title="Rotate Left 90° (counter-clockwise)"
								aria-label="Rotate Left 90°"
								@click="rotateProfile(-90)"
							>
								<svg viewBox="0 0 640 640" class="h-3.5 w-3.5" fill="currentColor" aria-hidden="true">
									<path d="M88 256L232 256C241.7 256 250.5 250.2 254.2 241.2C257.9 232.2 255.9 221.9 249 215L202.3 168.3C277.6 109.7 386.6 115 455.8 184.2C530.8 259.2 530.8 380.7 455.8 455.7C380.8 530.7 259.3 530.7 184.3 455.7C174.1 445.5 165.3 434.4 157.9 422.7C148.4 407.8 128.6 403.4 113.7 412.9C98.8 422.4 94.4 442.2 103.9 457.1C113.7 472.7 125.4 487.5 139 501C239 601 401 601 501 501C601 401 601 239 501 139C406.8 44.7 257.3 39.3 156.7 122.8L105 71C98.1 64.2 87.8 62.1 78.8 65.8C69.8 69.5 64 78.3 64 88L64 232C64 245.3 74.7 256 88 256z" />
								</svg>
							</button>
							<span class="min-w-10 border-x border-outline-gray-2 px-2 py-1 text-center font-mono text-xs font-bold text-blue-600">
								{{ form.section_rotation || '0' }}°
							</span>
							<button
								type="button"
								class="flex h-7 items-center justify-center px-2 text-xs font-semibold text-ink-gray-6 transition-colors hover:bg-surface-gray-3 hover:text-ink-gray-9"
								title="Rotate Right 90° (clockwise)"
								aria-label="Rotate Right 90°"
								@click="rotateProfile(90)"
							>
								<svg viewBox="0 0 640 640" class="h-3.5 w-3.5" fill="currentColor" aria-hidden="true">
									<path d="M552 256L408 256C398.3 256 389.5 250.2 385.8 241.2C382.1 232.2 384.1 221.9 391 215L437.7 168.3C362.4 109.7 253.4 115 184.2 184.2C109.2 259.2 109.2 380.7 184.2 455.7C259.2 530.7 380.7 530.7 455.7 455.7C463.9 447.5 471.2 438.8 477.6 429.6C487.7 415.1 507.7 411.6 522.2 421.7C536.7 431.8 540.2 451.8 530.1 466.3C521.6 478.5 511.9 490.1 501 501C401 601 238.9 601 139 501C39.1 401 39 239 139 139C233.3 44.7 382.7 39.4 483.3 122.8L535 71C541.9 64.1 552.2 62.1 561.2 65.8C570.2 69.5 576 78.3 576 88L576 232C576 245.3 565.3 256 552 256z" />
								</svg>
							</button>
						</div>

						<Button
							type="button"
							size="sm"
							variant="subtle"
							:loading="savingOrientation"
							title="Set current orientation as the default for this profile"
							@click="saveDefaultOrientation"
						>
							<template #prefix>
								<svg viewBox="0 0 16 16" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.6">
									<path d="M3 3h10v10H3z" stroke-linecap="round" stroke-linejoin="round" />
									<path d="M6 3v4h4V3" stroke-linecap="round" stroke-linejoin="round" />
								</svg>
							</template>
							Set as Default Orientation
						</Button>

						<div class="inline-flex overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-gray-1">
							<button
								type="button"
								class="px-3 py-1 text-xs font-semibold transition-colors"
								:class="showGrid ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-6'"
								@click="showGrid = !showGrid"
							>
								Grid
							</button>
							<button
								type="button"
								class="border-l border-outline-gray-2 px-3 py-1 text-xs font-semibold transition-colors"
								:class="showDims ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-6'"
								@click="showDims = !showDims"
							>
								Dimensions
							</button>
							<button
								type="button"
								class="border-l border-outline-gray-2 px-3 py-1 text-xs font-semibold transition-colors"
								:class="showCentroid ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-6'"
								@click="showCentroid = !showCentroid"
							>
								Centroid
							</button>
						</div>
						<Badge theme="green" label="Parsed" />
					</div>
				</div>

				<div
					v-if="hasSvg"
					class="flex min-h-[320px] items-center justify-center overflow-hidden rounded-xl border border-outline-gray-2 bg-slate-50"
				>
					<svg
						:viewBox="`0 0 ${metrics.cw} ${metrics.ch}`"
						class="block h-[320px] w-full"
						xmlns="http://www.w3.org/2000/svg"
					>
						<defs>
							<pattern
								id="profile-page-grid-min"
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
								id="profile-page-grid-maj"
								:width="metrics.majorPx"
								:height="metrics.majorPx"
								patternUnits="userSpaceOnUse"
								:patternTransform="`translate(${metrics.ox}, ${metrics.oy})`"
							>
								<rect :width="metrics.majorPx" :height="metrics.majorPx" fill="url(#profile-page-grid-min)" />
								<path
									:d="`M ${metrics.majorPx} 0 L 0 0 0 ${metrics.majorPx}`"
									fill="none"
									stroke="#cbd5e1"
									stroke-width="1.1"
								/>
							</pattern>
						</defs>

						<rect
							v-if="showGrid"
							x="0"
							y="0"
							:width="metrics.cw"
							:height="metrics.ch"
							fill="url(#profile-page-grid-maj)"
						/>

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
							<text
								:x="metrics.cx + 6.5"
								:y="metrics.cy - 2.5"
								fill="#2563eb"
								stroke="#f8fafc"
								stroke-width="3"
								paint-order="stroke"
								font-size="11.5"
								font-weight="600"
							>
								centroid
							</text>
						</g>
					</svg>
				</div>
				<div
					v-else
					class="rounded-xl border border-outline-gray-2 bg-slate-50 p-8 text-center text-ink-gray-5"
				>
					<div class="text-sm font-semibold text-ink-gray-8">No DXF Section Attached</div>
					<div class="mt-1 text-xs">
						Drag and drop a CAD <code>.dxf</code> file above to compute and preview its cross-section geometry.
					</div>
				</div>

				<!-- 6-Stat Engineering Summary Grid (from fenestration_profile.js) -->
				<div
					v-if="hasSvg"
					class="mt-3 grid grid-cols-1 gap-px overflow-hidden rounded-xl border border-outline-gray-2 bg-outline-gray-2 sm:grid-cols-2 lg:grid-cols-3"
				>
					<div class="bg-surface-white p-3.5">
						<div class="text-[11px] font-semibold uppercase tracking-wider text-ink-gray-5">Dimensions</div>
						<div class="mt-1 text-sm font-bold text-ink-gray-9">
							{{ formatMetric(form.width_mm, 1) }} × {{ formatMetric(form.depth_mm, 1) }}
							<span class="text-xs font-medium text-ink-gray-5">mm</span>
						</div>
						<div class="mt-0.5 text-[11px] text-ink-gray-5">Width × Depth bounding box</div>
					</div>
					<div class="bg-surface-white p-3.5">
						<div class="text-[11px] font-semibold uppercase tracking-wider text-ink-gray-5">Section Area</div>
						<div class="mt-1 text-sm font-bold text-ink-gray-9">
							{{ formatMetric(form.area_mm2, 1) }}
							<span class="text-xs font-medium text-ink-gray-5">mm²</span>
						</div>
						<div class="mt-0.5 text-[11px] text-ink-gray-5">Net metal (outer − chambers)</div>
					</div>
					<div class="bg-surface-white p-3.5">
						<div class="text-[11px] font-semibold uppercase tracking-wider text-ink-gray-5">Ix · Iy</div>
						<div class="mt-1 text-sm font-bold text-ink-gray-9">
							{{ formatMetric(form.ix_mm4, 0) }} · {{ formatMetric(form.iy_mm4, 0) }}
							<span class="text-xs font-medium text-ink-gray-5">mm⁴</span>
						</div>
						<div class="mt-0.5 text-[11px] text-ink-gray-5">Second moment about centroid</div>
					</div>
					<div class="bg-surface-white p-3.5">
						<div class="text-[11px] font-semibold uppercase tracking-wider text-ink-gray-5">Outer Perimeter</div>
						<div class="mt-1 text-sm font-bold text-ink-gray-9">
							{{ formatMetric(form.perimeter_mm, 0) }}
							<span class="text-xs font-medium text-ink-gray-5">mm</span>
						</div>
						<div class="mt-0.5 text-[11px] text-ink-gray-5">Exposed contour (paint / anodize)</div>
					</div>
					<div class="bg-surface-white p-3.5">
						<div class="text-[11px] font-semibold uppercase tracking-wider text-ink-gray-5">Total Perimeter</div>
						<div class="mt-1 text-sm font-bold text-ink-gray-9">
							{{ formatMetric(form.total_perimeter_mm, 0) }}
							<span class="text-xs font-medium text-ink-gray-5">mm</span>
						</div>
						<div class="mt-0.5 text-[11px] text-ink-gray-5">Outer + inner chamber walls</div>
					</div>
					<div class="bg-surface-white p-3.5">
						<div class="text-[11px] font-semibold uppercase tracking-wider text-ink-gray-5">Effective Weight</div>
						<div class="mt-1 text-sm font-bold text-ink-gray-9">
							{{ formatMetric(form.use_computed_weight && form.computed_kg_per_m ? form.computed_kg_per_m : form.kg_per_m, 3) }}
							<span class="text-xs font-medium text-ink-gray-5">kg/m</span>
						</div>
						<div class="mt-0.5 text-[11px] text-ink-gray-5">
							{{ form.use_computed_weight ? 'Using DXF computed (Al 2700 kg/m³)' : `Manual · DXF computed ${formatMetric(form.computed_kg_per_m, 3)} kg/m` }}
						</div>
					</div>
				</div>
			</section>

			<!-- Section 3: Computed Section Properties -->
			<section class="border-t border-outline-gray-2 pt-6">
				<h2 class="mb-4 text-base font-semibold text-ink-gray-9">Computed Section Properties</h2>

				<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
					<!-- Left Column -->
					<div class="space-y-4">
						<FormControl
							:model-value="formatMetric(form.area_mm2, 1)"
							label="Area (mm²)"
							disabled
						/>
						<FormControl
							:model-value="formatMetric(form.width_mm, 1)"
							label="Width (mm)"
							disabled
						/>
						<FormControl
							:model-value="formatMetric(form.depth_mm, 1)"
							label="Depth (mm)"
							disabled
						/>
						<FormControl
							:model-value="formatMetric(form.perimeter_mm, 1)"
							label="Outer Perimeter (mm)"
							disabled
						/>
						<FormControl
							:model-value="formatMetric(form.total_perimeter_mm, 1)"
							label="Total Perimeter (mm)"
							disabled
						/>
					</div>

					<!-- Right Column -->
					<div class="space-y-4">
						<FormControl
							:model-value="formatMetric(form.ix_mm4, 0)"
							label="Ix (mm⁴)"
							disabled
						/>
						<FormControl
							:model-value="formatMetric(form.iy_mm4, 0)"
							label="Iy (mm⁴)"
							disabled
						/>
						<FormControl
							:model-value="formatMetric(form.computed_kg_per_m, 3)"
							label="Computed Weight (kg/m)"
							disabled
						/>
						<div>
							<FormControl
								v-model.number="form.visible_perimeter_mm"
								type="number"
								step="0.1"
								label="Visible Perimeter (mm)"
								placeholder="e.g. 165.0"
							/>
							<p class="mt-1 text-xs text-ink-gray-5">
								Used for powder coating and wood finish pricing per visible perimeter.
							</p>
						</div>
						<FormControl
							:model-value="form.section_warnings || '—'"
							label="Section Warnings"
							disabled
						/>
					</div>
				</div>
			</section>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Alert, Badge, Button, Checkbox, Combobox, FormControl, toast, upload, useList } from 'frappe-ui'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
	getFenestrationProfileDoc,
	previewDxf,
	saveFenestrationProfile,
	setProfileOrientation,
	type FenestrationProfileRow,
	type ProfileSeriesRow,
} from '@/studio/api'
import { cleanDxfFilename, computeBlueprintSvgMetrics } from '@/studio/sectionSvg'

const props = defineProps<{ name?: string }>()
const route = useRoute()
const router = useRouter()

const isEdit = computed(() => Boolean(props.name))
const loadingDoc = ref(false)
const saving = ref(false)
const error = ref('')

const showGrid = ref(true)
const showDims = ref(true)
const showCentroid = ref(true)

const isDragging = ref(false)
const uploadingDxf = ref(false)
const uploadProgress = ref(0)
const parsingDxf = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const savingOrientation = ref(false)

const form = reactive<{
	name: string
	profile_code: string
	profile_name: string
	series: string
	role: FenestrationProfileRow['role']
	item: string
	bar_lengths: string
	kg_per_m: number
	dxf_file: string
	use_computed_weight: boolean
	area_mm2: number | null
	width_mm: number | null
	depth_mm: number | null
	raw_width_mm: number | null
	raw_depth_mm: number | null
	section_rotation: string
	perimeter_mm: number | null
	total_perimeter_mm: number | null
	visible_perimeter_mm: number | null
	ix_mm4: number | null
	iy_mm4: number | null
	computed_kg_per_m: number | null
	section_svg: string
	section_warnings: string
}>({
	name: '',
	profile_code: '',
	profile_name: '',
	series: String(route.query.series || ''),
	role: 'frame',
	item: '',
	bar_lengths: '4880, 5800',
	kg_per_m: 1.0,
	dxf_file: '',
	use_computed_weight: false,
	area_mm2: null,
	width_mm: null,
	depth_mm: null,
	raw_width_mm: null,
	raw_depth_mm: null,
	section_rotation: '0',
	perimeter_mm: null,
	total_perimeter_mm: null,
	visible_perimeter_mm: null,
	ix_mm4: null,
	iy_mm4: null,
	computed_kg_per_m: null,
	section_svg: '',
	section_warnings: '',
})

const seriesResource = useList<ProfileSeriesRow>({
	doctype: 'Profile Series',
	fields: ['name', 'series_code', 'series_title'],
	orderBy: 'series_code asc',
	limit: 200,
})

const itemsResource = useList<{ name: string; item_name?: string; fen_item_kind?: string }>({
	doctype: 'Item',
	fields: ['name', 'item_name', 'fen_item_kind'],
	limit: 500,
})

const seriesOptions = computed(() =>
	(seriesResource.data ?? []).map((s) => ({
		label: `${s.series_code || s.name} — ${s.series_title}`,
		value: s.series_code || s.name,
	})),
)

const roleOptions = [
	{ label: 'Frame', value: 'frame' },
	{ label: 'Sash', value: 'sash' },
	{ label: 'Mullion', value: 'mullion' },
	{ label: 'Transom', value: 'transom' },
	{ label: 'Bead', value: 'bead' },
	{ label: 'Accessory', value: 'accessory' },
]

const itemOptions = computed(() => {
	const all = itemsResource.data ?? []
	const sorted = [...all].sort((a, b) => {
		const aScore = a.fen_item_kind === 'Profile' ? 0 : 1
		const bScore = b.fen_item_kind === 'Profile' ? 0 : 1
		if (aScore !== bScore) return aScore - bScore
		return a.name.localeCompare(b.name)
	})
	return sorted.map((i) => ({
		label: i.item_name ? `${i.name} — ${i.item_name}` : i.name,
		value: i.name,
	}))
})

const hasSvg = computed(() => Boolean(form.section_svg && form.width_mm && form.depth_mm))

const unitNote = computed(() =>
	(form.section_warnings || '').includes('units_assumed_mm') ? 'Units read as mm' : 'Units in mm',
)

const metrics = computed(() => computeBlueprintSvgMetrics(form, showDims.value))

const canSave = computed(() =>
	Boolean(
		form.profile_code.trim() &&
			form.profile_name.trim() &&
			form.series &&
			form.role &&
			form.bar_lengths.trim() &&
			Number(form.kg_per_m) > 0 &&
			!saving.value &&
			!uploadingDxf.value &&
			!parsingDxf.value,
	),
)

const rotationTransform = computed(() => {
	const rot = (((Number(form.section_rotation || 0) % 360) + 360) % 360)
	const w0 = form.raw_width_mm ?? form.width_mm ?? 0
	const h0 = form.raw_depth_mm ?? form.depth_mm ?? 0
	if (rot === 90) return `translate(${h0}, 0) rotate(90)`
	if (rot === 180) return `translate(${w0}, ${h0}) rotate(180)`
	if (rot === 270) return `translate(0, ${w0}) rotate(270)`
	return ''
})

function rotateProfile(deltaDeg: number) {
	const cur = Number(form.section_rotation || 0)
	const next = (((cur + deltaDeg) % 360) + 360) % 360
	form.section_rotation = String(next)
	updateRotatedDimensions()
}

function updateRotatedDimensions() {
	if (form.raw_width_mm == null || form.raw_depth_mm == null) return
	const rot = (((Number(form.section_rotation || 0) % 360) + 360) % 360)
	const isTurned = rot === 90 || rot === 270
	form.width_mm = isTurned ? form.raw_depth_mm : form.raw_width_mm
	form.depth_mm = isTurned ? form.raw_width_mm : form.raw_depth_mm
}

async function saveDefaultOrientation() {
	if (!props.name) {
		toast.success(`Orientation set to ${form.section_rotation || '0'}° (will save with profile)`)
		return
	}
	savingOrientation.value = true
	try {
		const res = await setProfileOrientation(props.name, form.section_rotation)
		form.section_rotation = String(res.section_rotation)
		form.width_mm = res.width_mm
		form.depth_mm = res.depth_mm
		toast.success(`Default orientation set to ${res.section_rotation}°`)
	} catch (e) {
		toast.error(e instanceof Error ? e.message : 'Could not set default orientation')
	} finally {
		savingOrientation.value = false
	}
}

function formatMetric(val: number | null | undefined, dp: number): string {
	if (val == null || Number.isNaN(Number(val))) return '—'
	return Number(val).toFixed(dp)
}

onMounted(async () => {
	if (!props.name) return
	loadingDoc.value = true
	try {
		const doc = await getFenestrationProfileDoc(props.name)
		applyDoc(doc)
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Could not load profile'
	} finally {
		loadingDoc.value = false
	}
})

function applyDoc(doc: FenestrationProfileRow) {
	form.name = doc.name
	form.profile_code = doc.profile_code || doc.name
	form.profile_name = doc.profile_name || ''
	form.series = doc.series || ''
	form.role = doc.role || 'frame'
	form.item = doc.item || ''
	form.bar_lengths = doc.bar_lengths || '4880, 5800'
	form.kg_per_m = Number(doc.kg_per_m || 0)
	form.dxf_file = doc.dxf_file || ''
	form.use_computed_weight = Boolean(doc.use_computed_weight)
	form.area_mm2 = doc.area_mm2 ?? null
	form.section_rotation = String(doc.section_rotation || '0')
	const rot = (((Number(form.section_rotation || 0) % 360) + 360) % 360)
	const isTurned = rot === 90 || rot === 270
	form.raw_width_mm = isTurned ? (doc.depth_mm ?? null) : (doc.width_mm ?? null)
	form.raw_depth_mm = isTurned ? (doc.width_mm ?? null) : (doc.depth_mm ?? null)
	form.width_mm = doc.width_mm ?? null
	form.depth_mm = doc.depth_mm ?? null
	form.perimeter_mm = doc.perimeter_mm ?? null
	form.total_perimeter_mm = doc.total_perimeter_mm ?? null
	form.visible_perimeter_mm = doc.visible_perimeter_mm ?? null
	form.ix_mm4 = doc.ix_mm4 ?? null
	form.iy_mm4 = doc.iy_mm4 ?? null
	form.computed_kg_per_m = doc.computed_kg_per_m ?? null
	form.section_svg = doc.section_svg || ''
	form.section_warnings = doc.section_warnings || ''
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
		error.value = 'Please select a valid .dxf CAD section file.'
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
			form.section_rotation = '0'
			form.perimeter_mm = res.section.perimeter_mm
			form.total_perimeter_mm = res.section.total_perimeter_mm
			form.ix_mm4 = res.section.ix_mm4
			form.iy_mm4 = res.section.iy_mm4
			form.computed_kg_per_m = res.section.computed_kg_per_m
			form.section_svg = res.section.section_svg
			form.section_warnings = res.section.section_warnings
			if (!isEdit.value || form.use_computed_weight) {
				form.kg_per_m = res.section.computed_kg_per_m
			}
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
	form.area_mm2 = null
	form.width_mm = null
	form.depth_mm = null
	form.raw_width_mm = null
	form.raw_depth_mm = null
	form.section_rotation = '0'
	form.perimeter_mm = null
	form.total_perimeter_mm = null
	form.ix_mm4 = null
	form.iy_mm4 = null
	form.computed_kg_per_m = null
	form.section_svg = ''
	form.section_warnings = ''
}

function goBack() {
	router.push({
		path: '/series-studio',
		query: {
			tab: 'profiles',
			...(form.series ? { series: form.series } : {}),
		},
	})
}

async function save() {
	if (!canSave.value) return
	saving.value = true
	error.value = ''
	try {
		const saved = await saveFenestrationProfile(
			{
				profile_code: form.profile_code.trim(),
				profile_name: form.profile_name.trim(),
				series: form.series,
				role: form.role,
				item: form.item.trim() || null,
				bar_lengths: form.bar_lengths.trim(),
				kg_per_m: Number(form.kg_per_m),
				dxf_file: form.dxf_file || null,
				use_computed_weight: form.use_computed_weight,
				visible_perimeter_mm: form.visible_perimeter_mm,
				section_rotation: form.section_rotation || '0',
			},
			props.name || null,
		)
		applyDoc(saved)
		toast.success(isEdit.value ? 'Profile updated' : 'Profile created')
		if (!isEdit.value) {
			router.replace(`/series-studio/profiles/${encodeURIComponent(saved.name)}`)
		}
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Could not save fenestration profile'
	} finally {
		saving.value = false
	}
}
</script>

