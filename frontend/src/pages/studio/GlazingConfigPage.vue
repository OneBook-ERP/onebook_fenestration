<template>
	<div class="mx-auto max-w-[1180px] px-6 py-6">
		<!-- Clean Single-Row Header -->
		<header class="mb-6 flex items-start justify-between gap-6 border-b border-outline-gray-2 pb-5">
			<div class="min-w-0 flex-1">
				<nav aria-label="Breadcrumb" class="mb-1.5 flex items-center gap-1.5 text-xs text-ink-gray-5">
					<router-link to="/series-studio?tab=glass" class="hover:text-ink-gray-8">
						Series Studio
					</router-link>
					<span aria-hidden="true">/</span>
					<router-link to="/series-studio?tab=glass" class="hover:text-ink-gray-8">
						Fenestration Glass
					</router-link>
					<span aria-hidden="true">/</span>
					<span class="font-medium text-ink-gray-8">Bead &amp; Gasket Config</span>
				</nav>
				<div class="flex flex-wrap items-center gap-2.5">
					<h1 class="text-xl font-semibold tracking-tight text-ink-gray-9">
						Bead &amp; Gasket Configuration
					</h1>
					<Badge theme="blue" label="BW − GT = R Auto + Rules" />
					<Badge v-if="dirty" theme="amber" label="Unsaved" />
				</div>
				<p class="mt-1 max-w-2xl text-[13px] leading-relaxed text-ink-gray-5">
					Configure per-series Bead &amp; Pocket Widths (<code class="font-mono text-xs">BW</code>) so the engine automatically selects the tightest bead (<code class="font-mono text-xs">GT &lt; BW</code>) and splits <code class="font-mono text-xs">R = BW − GT</code> across two gaskets with the thicker gasket on the outer side.
				</p>
			</div>

			<div class="flex shrink-0 items-center gap-2.5 pt-1">
				<Button variant="outline" label="Back" route="/series-studio?tab=glass" />
				<Button
					variant="solid"
					label="Save Changes"
					:loading="saving"
					:disabled="saving || loading"
					data-testid="save-global-glazing-btn"
					@click="save"
				/>
			</div>
		</header>

		<div v-if="loading" class="py-20 text-center text-sm text-ink-gray-5">
			Loading bead &amp; gasket configuration…
		</div>

		<div v-else class="space-y-6">
			<Alert v-if="error" theme="red" :title="error" />

			<!-- ================================================================ -->
			<!-- 1. AUTO BEAD & GASKET WIDTH CALCULATOR (BW - GT = R)             -->
			<!-- ================================================================ -->
			<section
				data-testid="auto-glazing-section"
				class="overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white"
			>
				<!-- Card Header -->
				<div class="flex flex-wrap items-center justify-between gap-4 border-b border-outline-gray-2 bg-surface-gray-1/40 px-5 py-4">
					<div class="min-w-0 flex-1">
						<div class="flex flex-wrap items-center gap-2.5">
							<h2 class="text-[15px] font-semibold text-ink-gray-9">
								Auto Bead &amp; Gasket Calculator
							</h2>
							<Badge
								:theme="autoConfig.enabled ? 'green' : 'gray'"
								:label="autoConfig.enabled ? 'Active' : 'Paused'"
							/>
							<span class="rounded-md bg-surface-gray-2 px-2 py-0.5 font-mono text-[11px] font-medium text-ink-gray-7">
								BW − GT = R · Max Compression ≤ {{ autoConfig.max_compression_mm }} mm
							</span>
						</div>
						<p class="mt-1 text-xs text-ink-gray-5">
							When enabled, configured series widths take priority automatically; manual thickness rules below apply as fallback.
						</p>
					</div>

					<div class="flex items-center gap-3">
						<Switch
							v-model="autoConfig.enabled"
							size="sm"
							label="Enable Auto Solver"
							data-testid="auto-glazing-toggle"
							@update:model-value="dirty = true"
						/>
					</div>
				</div>

				<!-- Controls Bar: Series Selector + Fit Settings -->
				<div class="grid grid-cols-1 gap-4 border-b border-outline-gray-1 px-5 py-4 md:grid-cols-[minmax(240px,1.4fr)_180px_190px]">
					<div>
						<label class="mb-1.5 block text-xs font-medium text-ink-gray-7">
							Series Scope
						</label>
						<select
							v-model="selectedSeries"
							aria-label="Series scope"
							data-testid="auto-series-select"
							class="h-9 w-full rounded-lg border border-outline-gray-2 bg-surface-white px-3 py-0 text-[13px] leading-9 text-ink-gray-9 focus:border-blue-500 focus:outline-none"
						>
							<option value="">
								All Series (Default Fallback){{ channelCountForSeries('') ? ` · ${channelCountForSeries('')} widths` : '' }}
							</option>
							<option v-for="s in seriesList" :key="s.name" :value="s.series_code || s.name">
								{{ s.series_code || s.name }} · {{ s.series_title || s.name }}{{ channelCountForSeries(s.series_code || s.name) ? ` (${channelCountForSeries(s.series_code || s.name)} widths)` : '' }}
							</option>
						</select>
					</div>

					<div>
						<label class="mb-1.5 block text-xs font-medium text-ink-gray-7">
							Max Compression (mm)
						</label>
						<input
							v-model.number="autoConfig.max_compression_mm"
							type="number"
							step="0.1"
							min="0"
							max="5"
							aria-label="Max gasket compression mm"
							data-testid="auto-max-compression-input"
							class="h-9 w-full rounded-lg border border-outline-gray-2 bg-surface-white px-3 py-0 text-[13px] font-medium leading-9 text-ink-gray-9 focus:border-blue-500 focus:outline-none"
							@input="dirty = true"
						/>
					</div>

					<div>
						<label class="mb-1.5 block text-xs font-medium text-ink-gray-7">
							Thicker Gasket Placement
						</label>
						<select
							v-model="autoConfig.thicker_gasket_side"
							aria-label="Thicker gasket side"
							data-testid="auto-thicker-side-select"
							class="h-9 w-full rounded-lg border border-outline-gray-2 bg-surface-white px-3 py-0 text-[13px] leading-9 text-ink-gray-9 focus:border-blue-500 focus:outline-none"
							@change="dirty = true"
						>
							<option value="outer">Outer Side (Rebate / Frame)</option>
							<option value="inner">Inner Side (Bead Side)</option>
						</select>
					</div>
				</div>

				<!-- Available Gasket Pool Bar -->
				<div class="flex flex-wrap items-center justify-between gap-3 border-b border-outline-gray-1 bg-surface-gray-1/30 px-5 py-3">
					<div class="flex flex-wrap items-center gap-2">
						<span class="text-xs font-medium text-ink-gray-6">Gasket Pool:</span>
						<template v-if="sizedGaskets.length">
							<button
								v-for="g in sizedGaskets"
								:key="g.code"
								type="button"
								:data-testid="`gasket-pool-chip-${g.code}`"
								class="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors"
								:class="
									isGasketInPool(g.code)
										? 'border-blue-300 bg-blue-50 text-blue-900'
										: 'border-outline-gray-2 bg-surface-white text-ink-gray-5 hover:text-ink-gray-8'
								"
								@click="toggleGasketInPool(g.code)"
							>
								<span class="font-semibold">{{ g.code }}</span>
								<span class="font-mono text-[11px] opacity-80">{{ g.thickness_mm }} mm</span>
							</button>
						</template>
						<span v-else class="text-xs text-amber-700">
							No Gasket hardware with <code class="font-mono">thickness_mm</code> found. Set thickness in Gaskets &amp; Hardware.
						</span>
					</div>
					<router-link
						to="/series-studio?tab=hardware"
						class="shrink-0 text-xs font-medium text-blue-600 hover:underline"
					>
						Manage Gasket Sizes →
					</router-link>
				</div>

				<!-- Bead & Pocket Widths (BW) List for Selected Series -->
				<div class="px-5 py-4">
					<div class="mb-3 flex flex-wrap items-center justify-between gap-2">
						<div>
							<h3 class="text-[13px] font-semibold text-ink-gray-9">
								Bead &amp; Pocket Widths (<code class="font-mono text-xs">BW</code>)
								<span class="font-normal text-ink-gray-5">
									— {{ selectedSeries || 'All Series (Default)' }}
								</span>
							</h3>
							<p class="mt-0.5 text-xs text-ink-gray-5">
								Add each bead profile with its bead width (<code class="font-mono text-[11px]">BW</code>), plus a No Bead pocket width (e.g. sash width <code class="font-mono text-[11px]">28 mm</code>) for thick DGU or window sashes.
							</p>
						</div>

						<div class="flex flex-wrap items-center gap-2">
							<Button
								variant="outline"
								size="sm"
								label="+ Add Bead Width"
								data-testid="add-auto-bead-btn"
								@click="addAutoChannel(false)"
							/>
							<Button
								variant="outline"
								size="sm"
								label="+ Add Pocket (No Bead)"
								data-testid="add-auto-pocket-btn"
								@click="addAutoChannel(true)"
							/>
						</div>
					</div>

					<div
						v-if="!activeSeriesChannels.length"
						class="rounded-lg border border-dashed border-outline-gray-3 bg-surface-gray-1/30 px-5 py-7 text-center"
					>
						<p class="text-[13px] font-medium text-ink-gray-8">
							No bead or pocket widths configured for {{ selectedSeries || 'All Series (Default)' }} yet
						</p>
						<p class="mx-auto mt-1 max-w-lg text-xs text-ink-gray-5">
							{{
								selectedSeries && channelCountForSeries('') > 0
									? `This series currently inherits ${channelCountForSeries('')} width(s) from All Series (Default). Add widths here to customize ${selectedSeries}.`
									: 'Add your bead widths (e.g. 12.01 mm, 18.01 mm) and sash pocket width (e.g. 28 mm No Bead) to auto-select beads and gaskets for every glass thickness.'
							}}
						</p>
					</div>

					<div v-else class="overflow-x-auto rounded-lg border border-outline-gray-2">
						<table class="w-full min-w-[780px] border-collapse text-left text-xs">
							<thead>
								<tr class="border-b border-outline-gray-2 bg-surface-gray-1/60 text-[11px] font-semibold uppercase tracking-wider text-ink-gray-5">
									<th class="px-3.5 py-2.5">Bead / Pocket</th>
									<th class="w-[130px] px-3 py-2.5">Width BW (mm)</th>
									<th class="w-[145px] px-3 py-2.5">Profile Type</th>
									<th class="w-[145px] px-3 py-2.5">Applies To</th>
									<th class="w-[115px] px-3 py-2.5">Bead Side</th>
									<th class="w-[60px] px-3 py-2.5 text-right">Action</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-outline-gray-1">
								<tr
									v-for="ch in activeSeriesChannels"
									:key="ch.id"
									data-testid="auto-channel-row"
									class="bg-surface-white hover:bg-surface-gray-1/30"
								>
									<!-- Bead / Pocket Selector -->
									<td class="px-3.5 py-2.5">
										<div class="flex items-center gap-2.5">
											<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-outline-gray-2 bg-[#f7f7f5] p-1">
												<svg
													v-if="!ch.no_bead && beadSvgFor(ch.bead_profile)"
													:viewBox="beadViewBoxFor(ch.bead_profile)"
													class="h-full w-full"
												>
													<path
														:d="beadSvgFor(ch.bead_profile)!"
														fill="#94a3b8"
														stroke="#334155"
														stroke-width="0.9"
														fill-rule="evenodd"
													/>
												</svg>
												<span v-else class="text-[10px] font-medium text-ink-gray-4">NB</span>
											</div>
											<select
												:value="ch.no_bead ? '' : ch.bead_profile"
												aria-label="Channel bead profile"
												data-testid="auto-channel-bead-select"
												class="h-8 w-full min-w-[200px] rounded-md border border-outline-gray-2 bg-surface-white px-2.5 py-0 text-xs leading-8 text-ink-gray-9 focus:border-blue-500 focus:outline-none"
												@change="onAutoChannelBeadChange(ch, ($event.target as HTMLSelectElement).value)"
											>
												<option value="">None (No Bead — Sash / Frame Pocket)</option>
												<optgroup
													v-if="seriesSpecificBeadOptions.length"
													:label="`${selectedSeries} Beads`"
												>
													<option
														v-for="b in seriesSpecificBeadOptions"
														:key="`s-${b.code}`"
														:value="b.code"
													>
														{{ b.code }} · {{ b.label }}
													</option>
												</optgroup>
												<optgroup label="All Bead Profiles">
													<option v-for="b in beadOptions" :key="`a-${b.code}`" :value="b.code">
														{{ b.code }} · {{ b.label }}
													</option>
												</optgroup>
											</select>
										</div>
									</td>

									<!-- Bead / Pocket Width (BW) -->
									<td class="px-3 py-2.5">
										<input
											v-model.number="ch.bead_width_mm"
											type="number"
											step="0.01"
											min="0"
											placeholder="e.g. 12.01"
											aria-label="Bead or pocket width mm"
											data-testid="auto-channel-bw-input"
											class="h-8 w-full rounded-md border border-outline-gray-2 bg-surface-white px-2.5 py-0 font-mono text-xs font-semibold leading-8 text-ink-gray-9 focus:border-blue-500 focus:outline-none"
											@input="dirty = true"
										/>
									</td>

									<!-- Profile Type -->
									<td class="px-3 py-2.5">
										<select
											v-model="ch.profile_type"
											aria-label="Channel profile type"
											class="h-8 w-full rounded-md border border-outline-gray-2 bg-surface-white px-2 py-0 text-xs leading-8 text-ink-gray-9 focus:border-blue-500 focus:outline-none"
											@change="dirty = true"
										>
											<option value="both">Door &amp; Window</option>
											<option value="window">Window Only</option>
											<option value="door">Door Only</option>
										</select>
									</td>

									<!-- Host -->
									<td class="px-3 py-2.5">
										<select
											v-model="ch.host"
											aria-label="Channel host"
											data-testid="auto-channel-host-select"
											class="h-8 w-full rounded-md border border-outline-gray-2 bg-surface-white px-2 py-0 text-xs leading-8 text-ink-gray-9 focus:border-blue-500 focus:outline-none"
											@change="dirty = true"
										>
											<option value="frame">Frame</option>
											<option value="sash">Sash</option>
											<option value="both">Frame &amp; Sash</option>
										</select>
									</td>

									<!-- Bead Side -->
									<td class="px-3 py-2.5">
										<select
											v-if="!ch.no_bead"
											v-model="ch.bead_side"
											aria-label="Channel bead side"
											class="h-8 w-full rounded-md border border-outline-gray-2 bg-surface-white px-2 py-0 text-xs leading-8 text-ink-gray-9 focus:border-blue-500 focus:outline-none"
											@change="dirty = true"
										>
											<option value="inside">Inside</option>
											<option value="outside">Outside</option>
										</select>
										<span v-else class="text-xs text-ink-gray-4">Pocket</span>
									</td>

									<!-- Remove -->
									<td class="px-3 py-2.5 text-right">
										<button
											type="button"
											class="rounded-md px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
											@click="removeAutoChannel(ch)"
										>
											Remove
										</button>
									</td>
								</tr>
							</tbody>
						</table>
					</div>

					<!-- Live Resolution Preview Matrix -->
					<div
						v-if="hasEffectiveAutoChannels"
						data-testid="auto-preview-matrix"
						class="mt-5 rounded-lg border border-outline-gray-2 bg-surface-gray-1/30"
					>
						<div class="flex flex-wrap items-center justify-between gap-3 border-b border-outline-gray-2 px-4 py-3">
							<div class="flex flex-wrap items-center gap-2">
								<span class="text-xs font-semibold text-ink-gray-8">Live Resolution Preview</span>
								<div class="inline-flex rounded-md border border-outline-gray-2 bg-surface-white p-0.5">
									<button
										v-for="ctx in previewContexts"
										:key="ctx.key"
										type="button"
										:data-testid="`preview-ctx-${ctx.key}`"
										class="rounded px-2.5 py-1 text-[11px] font-medium transition-colors"
										:class="
											previewContext === ctx.key
												? 'bg-blue-50 text-blue-900'
												: 'text-ink-gray-6 hover:text-ink-gray-9'
										"
										@click="previewContext = ctx.key"
									>
										{{ ctx.label }}
									</button>
								</div>
							</div>

							<div class="flex items-center gap-2">
								<label class="text-[11px] font-medium text-ink-gray-6" for="custom-gt-probe">
									Test GT (mm):
								</label>
								<input
									id="custom-gt-probe"
									v-model="customProbeThickness"
									type="number"
									step="0.5"
									min="1"
									placeholder="e.g. 13.5"
									data-testid="auto-probe-gt-input"
									class="h-7 w-24 rounded-md border border-outline-gray-2 bg-surface-white px-2 font-mono text-xs text-ink-gray-9 focus:border-blue-500 focus:outline-none"
								/>
							</div>
						</div>

						<div class="overflow-x-auto">
							<table class="w-full min-w-[700px] border-collapse text-left text-xs">
								<thead>
									<tr class="border-b border-outline-gray-2 bg-surface-gray-1/60 text-[11px] font-semibold uppercase tracking-wider text-ink-gray-5">
										<th class="px-4 py-2">Glass (GT)</th>
										<th class="px-3 py-2">Selected Bead / Pocket (BW)</th>
										<th class="px-3 py-2">R = BW − GT</th>
										<th class="px-3 py-2">Outer Gasket (Thicker)</th>
										<th class="px-3 py-2">Inner Gasket</th>
										<th class="px-4 py-2 text-right">Fit Status</th>
									</tr>
								</thead>
								<tbody class="divide-y divide-outline-gray-1 bg-surface-white">
									<tr
										v-for="row in previewRows"
										:key="row.key"
										data-testid="auto-preview-row"
									>
										<td class="px-4 py-2.5">
											<span class="font-mono font-semibold text-ink-gray-9">{{ row.thickness }} mm</span>
											<span class="ml-1.5 text-ink-gray-5">{{ row.label }}</span>
										</td>
										<template v-if="row.res && row.res.ok">
											<td class="px-3 py-2.5">
												<span class="font-semibold text-ink-gray-9">
													{{ row.res.no_bead ? 'No Bead (Pocket)' : row.res.bead_profile }}
												</span>
												<span class="ml-1.5 font-mono text-[11px] text-ink-gray-5">
													BW {{ row.res.bead_width_mm }} mm
												</span>
											</td>
											<td class="px-3 py-2.5 font-mono text-ink-gray-8">
												{{ row.res.remaining_mm }} mm
											</td>
											<td class="px-3 py-2.5">
												<span class="font-semibold text-ink-gray-9">{{ row.res.outer_gasket_hardware }}</span>
												<span class="ml-1 font-mono text-[11px] text-ink-gray-5">({{ row.res.outer_gasket_mm }} mm)</span>
											</td>
											<td class="px-3 py-2.5">
												<span class="font-semibold text-ink-gray-9">{{ row.res.inner_gasket_hardware }}</span>
												<span class="ml-1 font-mono text-[11px] text-ink-gray-5">({{ row.res.inner_gasket_mm }} mm)</span>
											</td>
											<td class="px-4 py-2.5 text-right">
												<span
													v-if="Math.abs(row.res.compression_mm) <= autoConfig.loose_tolerance_mm + 0.001"
													class="inline-flex rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700"
												>
													Exact fit
												</span>
												<span
													v-else
													class="inline-flex rounded-md bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700"
												>
													+{{ row.res.compression_mm }} mm tight
												</span>
											</td>
										</template>
										<template v-else-if="row.res && !row.res.ok">
											<td colspan="4" class="px-3 py-2.5 text-amber-800">
												{{ row.res.message }}
											</td>
											<td class="px-4 py-2.5 text-right">
												<span class="inline-flex rounded-md bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-800">
													No fit
												</span>
											</td>
										</template>
										<template v-else>
											<td colspan="5" class="px-3 py-2.5 text-ink-gray-4">
												No width channels configured for this host/type — uses manual rules below.
											</td>
										</template>
									</tr>
								</tbody>
							</table>
						</div>
					</div>
				</div>
			</section>

			<!-- ================================================================ -->
			<!-- 2. MANUAL THICKNESS RANGE RULES (FALLBACK / OVERRIDES)           -->
			<!-- ================================================================ -->
			<div class="space-y-4">
				<!-- Minimal Summary & Action Bar -->
				<div class="flex flex-wrap items-center justify-between gap-3">
					<div class="flex flex-wrap items-center gap-2.5 text-[13px] text-ink-gray-6">
						<span class="font-semibold text-ink-gray-9">Manual Thickness Rules</span>
						<span class="text-outline-gray-3">·</span>
						<span>
							<strong class="font-semibold text-ink-gray-9">{{ rules.length }}</strong>
							rule{{ rules.length === 1 ? '' : 's' }}
						</span>
						<span class="text-outline-gray-3">·</span>
						<span>
							<strong class="font-semibold text-ink-gray-9">{{ coveredGlassCount }}</strong> of {{ glasses.length }} glasses covered
						</span>
						<span class="text-outline-gray-3">·</span>
						<router-link
							to="/series-studio?tab=hardware"
							class="text-[13px] font-medium text-blue-600 hover:text-blue-700 hover:underline"
						>
							Gaskets &amp; Hardware →
						</router-link>
					</div>

					<div class="flex items-center gap-2">
						<Button
							v-if="!rules.length"
							variant="subtle"
							size="sm"
							label="Auto-fill Standard Ranges"
							data-testid="autofill-glazing-rules-btn"
							@click="autoFillStandardRanges"
						/>
						<Button
							variant="outline"
							size="sm"
							label="+ Add Rule"
							data-testid="add-global-rule-btn"
							@click="addRule('both')"
						/>
					</div>
				</div>

				<!-- Empty State -->
				<div
					v-if="!rules.length"
					class="rounded-xl border border-dashed border-outline-gray-3 bg-surface-gray-1/40 px-6 py-10 text-center"
				>
					<p class="text-sm font-semibold text-ink-gray-8">No manual thickness rules configured</p>
					<p class="mx-auto mt-1.5 max-w-md text-[13px] text-ink-gray-5">
						Optional fallback rules by thickness range for series that do not use Auto Bead &amp; Pocket Widths above.
					</p>
					<div class="mt-4 flex items-center justify-center gap-2.5">
						<Button variant="solid" size="sm" label="Auto-fill Standard Ranges" @click="autoFillStandardRanges" />
						<Button variant="outline" size="sm" label="+ Add Rule" @click="addRule('both')" />
					</div>
				</div>

				<!-- Two Clean Collapsible Accordions: Window & Door -->
				<div v-else class="space-y-4">
					<section
						v-for="sec in accordionSections"
						:key="sec.key"
						:data-testid="`accordion-${sec.key}`"
						class="overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-white"
					>
						<!-- Accordion Header -->
						<div
							class="flex cursor-pointer items-center justify-between gap-4 px-5 py-3.5 transition-colors hover:bg-surface-gray-1/50"
							:class="openAccordions[sec.key] ? 'border-b border-outline-gray-2' : ''"
							@click="toggleAccordion(sec.key)"
						>
							<div class="flex min-w-0 items-center gap-3">
								<svg
									viewBox="0 0 16 16"
									class="size-4 shrink-0 text-ink-gray-5 transition-transform duration-150"
									:class="openAccordions[sec.key] ? 'rotate-90' : ''"
									fill="none"
									stroke="currentColor"
									stroke-width="1.8"
									aria-hidden="true"
								>
									<path d="M6 3.5L10.5 8L6 12.5" stroke-linecap="round" stroke-linejoin="round" />
								</svg>
								<div class="min-w-0">
									<div class="flex items-center gap-2.5">
										<h2 class="text-[15px] font-semibold text-ink-gray-9">{{ sec.title }}</h2>
										<span
											class="rounded-md px-2 py-0.5 text-[11px] font-semibold"
											:class="sec.key === 'window' ? 'bg-blue-50 text-blue-700' : 'bg-amber-50 text-amber-800'"
										>
											{{ sec.rules.length }} rule{{ sec.rules.length === 1 ? '' : 's' }}
										</span>
									</div>
									<p class="mt-0.5 text-xs text-ink-gray-5">{{ sec.subtitle }}</p>
								</div>
							</div>

							<Button
								variant="outline"
								size="sm"
								:label="`+ Add ${sec.title} Rule`"
								:data-testid="`add-${sec.key}-rule-btn`"
								@click.stop="addRule(sec.key)"
							/>
						</div>

						<!-- Accordion Body -->
						<div v-if="openAccordions[sec.key]">
							<div
								v-if="!sec.rules.length"
								class="px-5 py-8 text-center text-xs text-ink-gray-5"
							>
								No {{ sec.title.toLowerCase() }} rules yet. Click
								<button
									type="button"
									class="font-semibold text-blue-600 hover:underline"
									@click="addRule(sec.key)"
								>
									+ Add {{ sec.title }} Rule
								</button>
								to create one.
							</div>

							<template v-else>
								<!-- Column Header -->
								<div
									class="grid grid-cols-[155px_minmax(220px,1.4fr)_minmax(155px,1fr)_minmax(155px,1fr)_110px_80px] items-center gap-4 border-b border-outline-gray-1 bg-surface-gray-1/60 px-5 py-2 text-[11px] font-semibold uppercase tracking-wider text-ink-gray-5"
								>
									<span>Glass Range</span>
									<span>Beading</span>
									<span>Inner Gasket</span>
									<span>Outer Gasket</span>
									<span>Applies To</span>
									<span class="text-right">Action</span>
								</div>

								<!-- Rules List -->
								<ul class="divide-y divide-outline-gray-1">
									<li
										v-for="rule in sec.rules"
										:key="`${sec.key}-${rule.id}`"
										data-testid="global-glazing-rule-card"
									>
										<!-- Scannable Summary Row -->
										<div
											class="grid cursor-pointer grid-cols-[155px_minmax(220px,1.4fr)_minmax(155px,1fr)_minmax(155px,1fr)_110px_80px] items-center gap-4 px-5 py-4 transition-colors"
											:class="isEditing(sec.key, rule) ? 'bg-blue-50/40' : 'hover:bg-surface-gray-1/60'"
											@click="toggleEdit(sec.key, rule)"
										>
											<!-- Thickness Range + Shared Pill -->
											<div class="min-w-0">
												<div class="flex items-center gap-1.5 font-mono text-[14px] font-semibold tracking-tight text-ink-gray-9">
													<span>{{ rule.min_glass_mm }} – {{ rule.max_glass_mm }}</span>
													<span class="font-sans text-xs font-normal text-ink-gray-5">mm</span>
												</div>
												<div class="mt-0.5 flex items-center gap-1.5 text-xs">
													<span :class="matchingGlasses(rule).length ? 'text-ink-gray-5' : 'text-amber-700'">
														{{ matchingGlasses(rule).length }} glass{{ matchingGlasses(rule).length === 1 ? '' : 'es' }}
													</span>
													<span
														v-if="(rule.profile_type || 'both') === 'both'"
														class="rounded bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-700"
													>
														Shared
													</span>
												</div>
											</div>

											<!-- Beading (or None) -->
											<div class="flex min-w-0 items-center gap-3">
												<div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-outline-gray-2 bg-[#f7f7f5] p-1.5">
													<svg
														v-if="!isNoBead(rule) && beadSvgFor(rule.bead_profile)"
														:viewBox="beadViewBoxFor(rule.bead_profile)"
														class="h-full w-full"
													>
														<path
															:d="beadSvgFor(rule.bead_profile)!"
															fill="#94a3b8"
															stroke="#334155"
															stroke-width="0.9"
															fill-rule="evenodd"
														/>
													</svg>
													<span v-else class="text-[11px] text-ink-gray-4">—</span>
												</div>
												<div class="min-w-0">
													<template v-if="isNoBead(rule)">
														<div class="truncate text-[13px] font-semibold text-ink-gray-6">
															None
														</div>
														<div class="mt-0.5 truncate text-xs text-ink-gray-4">
															No beading (gaskets only)
														</div>
													</template>
													<template v-else>
														<div class="truncate text-[13px] font-semibold text-ink-gray-9">
															{{ rule.bead_profile }}
														</div>
														<div class="mt-0.5 truncate text-xs text-ink-gray-5">
															{{ beadShortName(rule.bead_profile) }}
															<span class="mx-1 text-outline-gray-3">·</span>
															<span class="capitalize">{{ rule.bead_side }}</span>
														</div>
													</template>
												</div>
											</div>

											<!-- Inner Gasket -->
											<div class="flex min-w-0 items-center gap-2.5">
												<div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-outline-gray-2 bg-[#f7f7f5] p-1.5">
													<svg
														v-if="gasketSvgFor(rule.inner_gasket_hardware || rule.inner_gasket_item)"
														:viewBox="gasketViewBoxFor(rule.inner_gasket_hardware || rule.inner_gasket_item)"
														class="h-full w-full"
													>
														<path
															:d="gasketSvgFor(rule.inner_gasket_hardware || rule.inner_gasket_item)!"
															fill="#64748b"
															stroke="#0f172a"
															stroke-width="0.4"
															fill-rule="evenodd"
														/>
													</svg>
													<span v-else class="text-[11px] text-ink-gray-4">—</span>
												</div>
												<div class="min-w-0">
													<div class="truncate text-[13px] font-semibold text-ink-gray-9">
														{{ rule.inner_gasket_hardware || rule.inner_gasket_item || 'None' }}
													</div>
													<div class="mt-0.5 truncate text-xs text-ink-gray-5">
														{{ gasketSubLabel(rule.inner_gasket_hardware || rule.inner_gasket_item) }}
													</div>
												</div>
											</div>

											<!-- Outer Gasket -->
											<div class="flex min-w-0 items-center gap-2.5">
												<div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-outline-gray-2 bg-[#f7f7f5] p-1.5">
													<svg
														v-if="gasketSvgFor(rule.outer_gasket_hardware || rule.outer_gasket_item)"
														:viewBox="gasketViewBoxFor(rule.outer_gasket_hardware || rule.outer_gasket_item)"
														class="h-full w-full"
													>
														<path
															:d="gasketSvgFor(rule.outer_gasket_hardware || rule.outer_gasket_item)!"
															fill="#64748b"
															stroke="#0f172a"
															stroke-width="0.4"
															fill-rule="evenodd"
														/>
													</svg>
													<span v-else class="text-[11px] text-ink-gray-4">—</span>
												</div>
												<div class="min-w-0">
													<div class="truncate text-[13px] font-semibold text-ink-gray-9">
														{{ rule.outer_gasket_hardware || rule.outer_gasket_item || 'None' }}
													</div>
													<div class="mt-0.5 truncate text-xs text-ink-gray-5">
														{{ gasketSubLabel(rule.outer_gasket_hardware || rule.outer_gasket_item) }}
													</div>
												</div>
											</div>

											<!-- Applies To -->
											<div>
												<span class="inline-flex rounded-md bg-surface-gray-1 px-2.5 py-1 text-xs font-medium text-ink-gray-7">
													{{ hostLabel(rule.host) }}
												</span>
											</div>

											<!-- Edit Action -->
											<div class="flex justify-end">
												<Button
													:variant="isEditing(sec.key, rule) ? 'subtle' : 'outline'"
													size="sm"
													:label="isEditing(sec.key, rule) ? 'Done' : 'Edit'"
													@click.stop="toggleEdit(sec.key, rule)"
												/>
											</div>
										</div>

										<!-- Clean Spacious Inline Editor Panel -->
										<div
											v-if="isEditing(sec.key, rule)"
											data-testid="global-rule-editor"
											class="border-t border-blue-100 bg-surface-gray-1/50 px-5 py-5"
										>
											<div class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
												<!-- 1. Profile Type -->
												<div>
													<label class="mb-1.5 block text-xs font-medium text-ink-gray-7">
														Profile Type
													</label>
													<select
														:value="rule.profile_type || 'both'"
														aria-label="Profile type"
														data-testid="rule-profile-type-select"
														class="h-9 w-full rounded-lg border border-outline-gray-2 bg-surface-white px-3 py-0 text-[13px] leading-9 text-ink-gray-9 focus:border-blue-500 focus:outline-none"
														@change="onProfileTypeChange(rule, ($event.target as HTMLSelectElement).value as GlobalGlazingProfileType, sec.key)"
													>
														<option value="both">Door &amp; Window</option>
														<option value="window">Only Window</option>
														<option value="door">Only Door</option>
													</select>
												</div>

												<!-- 2. Profile Section / Beading Profile (with None) -->
												<div>
													<label class="mb-1.5 block text-xs font-medium text-ink-gray-7">
														Beading Profile
													</label>
													<select
														:value="isNoBead(rule) ? '' : rule.bead_profile"
														aria-label="Beading profile"
														data-testid="rule-bead-profile-select"
														class="h-9 w-full rounded-lg border border-outline-gray-2 bg-surface-white px-3 py-0 text-[13px] leading-9 text-ink-gray-9 focus:border-blue-500 focus:outline-none"
														@change="onBeadProfileChange(rule, ($event.target as HTMLSelectElement).value)"
													>
														<option value="">None (No Beading)</option>
														<option v-for="b in beadOptions" :key="b.code" :value="b.code">
															{{ b.code }} · {{ b.label }}
														</option>
													</select>
												</div>

												<!-- 3. Applies To -->
												<div>
													<label class="mb-1.5 block text-xs font-medium text-ink-gray-7">
														Applies To
													</label>
													<select
														v-model="rule.host"
														aria-label="Applies to"
														data-testid="rule-host-select"
														class="h-9 w-full rounded-lg border border-outline-gray-2 bg-surface-white px-3 py-0 text-[13px] leading-9 text-ink-gray-9 focus:border-blue-500 focus:outline-none"
														@change="dirty = true"
													>
														<option value="frame">Frame</option>
														<option value="sash">Sash</option>
														<option v-if="rule.host === 'both'" value="both">Frame &amp; Sash</option>
													</select>
												</div>

												<!-- 4. Glass Thickness Range -->
												<div>
													<label class="mb-1.5 block text-xs font-medium text-ink-gray-7">
														Glass Thickness Range (mm)
													</label>
													<div class="flex items-center gap-2">
														<input
															v-model.number="rule.min_glass_mm"
															type="number"
															step="0.5"
															min="0"
															aria-label="Min glass mm"
															class="h-9 w-full rounded-lg border border-outline-gray-2 bg-surface-white px-3 py-0 text-[13px] font-medium leading-9 text-ink-gray-9 focus:border-blue-500 focus:outline-none"
															@input="dirty = true"
														/>
														<span class="text-xs font-medium text-ink-gray-4">to</span>
														<input
															v-model.number="rule.max_glass_mm"
															type="number"
															step="0.5"
															min="0"
															aria-label="Max glass mm"
															class="h-9 w-full rounded-lg border border-outline-gray-2 bg-surface-white px-3 py-0 text-[13px] font-medium leading-9 text-ink-gray-9 focus:border-blue-500 focus:outline-none"
															@input="dirty = true"
														/>
													</div>
												</div>

												<!-- 5. Inner Glazing Gasket -->
												<div>
													<label class="mb-1.5 block text-xs font-medium text-ink-gray-7">
														{{ isNoBead(rule) ? 'Inner Glazing Gasket' : 'Inner Glazing Gasket (Bead Side)' }}
													</label>
													<select
														:value="rule.inner_gasket_hardware || rule.inner_gasket_item"
														aria-label="Inner glazing gasket"
														class="h-9 w-full rounded-lg border border-outline-gray-2 bg-surface-white px-3 py-0 text-[13px] leading-9 text-ink-gray-9 focus:border-blue-500 focus:outline-none"
														@change="onSelectGasket(rule, 'inner', ($event.target as HTMLSelectElement).value)"
													>
														<option value="">None</option>
														<option v-for="g in gasketOptions" :key="g.value" :value="g.value">
															{{ g.label }}
														</option>
													</select>
												</div>

												<!-- 6. Outer Glazing Gasket -->
												<div>
													<label class="mb-1.5 block text-xs font-medium text-ink-gray-7">
														Outer Glazing Gasket (Frame / Rebate Side)
													</label>
													<select
														:value="rule.outer_gasket_hardware || rule.outer_gasket_item"
														aria-label="Outer glazing gasket"
														class="h-9 w-full rounded-lg border border-outline-gray-2 bg-surface-white px-3 py-0 text-[13px] leading-9 text-ink-gray-9 focus:border-blue-500 focus:outline-none"
														@change="onSelectGasket(rule, 'outer', ($event.target as HTMLSelectElement).value)"
													>
														<option value="">None</option>
														<option v-for="g in gasketOptions" :key="g.value" :value="g.value">
															{{ g.label }}
														</option>
													</select>
												</div>
											</div>

											<!-- Secondary Row: Bead Side (only when a bead is chosen) + Remove -->
											<div class="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-outline-gray-2/70 pt-3.5">
												<div v-if="!isNoBead(rule)" class="flex items-center gap-3">
													<span class="text-xs font-medium text-ink-gray-6">Bead Side</span>
													<div class="inline-grid h-8 grid-cols-2 rounded-lg border border-outline-gray-2 bg-surface-white p-0.5">
														<button
															type="button"
															class="rounded-md px-3 text-xs font-medium transition-colors"
															:class="
																rule.bead_side === 'inside'
																	? 'bg-blue-50 text-blue-900'
																	: 'text-ink-gray-6 hover:text-ink-gray-9'
															"
															@click="setBeadSide(rule, 'inside')"
														>
															Inside
														</button>
														<button
															type="button"
															class="rounded-md px-3 text-xs font-medium transition-colors"
															:class="
																rule.bead_side === 'outside'
																	? 'bg-blue-50 text-blue-900'
																	: 'text-ink-gray-6 hover:text-ink-gray-9'
															"
															@click="setBeadSide(rule, 'outside')"
														>
															Outside
														</button>
													</div>
												</div>
												<div v-else class="text-xs text-ink-gray-5">
													No beading profile — glass is held directly by inner &amp; outer gaskets.
												</div>

												<button
													type="button"
													class="inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50"
													@click="removeRule(rule)"
												>
													<span class="lucide-trash-2 size-3.5" />
													Remove Rule
												</button>
											</div>

											<!-- Matched Glasses Preview -->
											<div class="mt-3 flex flex-wrap items-center gap-1.5 border-t border-outline-gray-2/60 pt-3">
												<span class="mr-1 text-xs text-ink-gray-5">Matches:</span>
												<template v-if="matchingGlasses(rule).length">
													<span
														v-for="g in matchingGlasses(rule)"
														:key="g.name"
														class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-0.5 text-xs text-ink-gray-7"
													>
														{{ g.glass_code || g.name }} ({{ g.thickness_mm }} mm)
													</span>
												</template>
												<span v-else class="text-xs text-amber-700">
													No glasses currently in this thickness range
												</span>
											</div>
										</div>
									</li>
								</ul>
							</template>
						</div>
					</section>
				</div>

				<!-- Subtle Uncovered Glasses Bar -->
				<div
					v-if="rules.length && uncoveredGlasses.length"
					class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200/80 bg-amber-50/50 px-4 py-3 text-xs text-amber-900"
				>
					<div class="flex flex-wrap items-center gap-1.5">
						<span class="font-semibold">Uncovered thickness (manual rules):</span>
						<span
							v-for="g in uncoveredGlasses"
							:key="g.name"
							class="rounded-md bg-white/90 px-2 py-0.5 text-[11px] font-medium text-amber-950"
						>
							{{ g.glass_code || g.name }} · {{ g.thickness_mm }} mm
						</span>
					</div>
					<button
						type="button"
						class="shrink-0 font-semibold text-amber-900 hover:underline"
						@click="addRuleForThickness(uncoveredGlasses[0].thickness_mm)"
					>
						+ Add rule for {{ uncoveredGlasses[0].thickness_mm }} mm
					</button>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Alert, Badge, Button, Switch, toast } from 'frappe-ui'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
	getGlobalGlazingRules,
	saveGlobalGlazingRules,
	type FenestrationGlassRow,
	type FenestrationHardwareRow,
	type FenestrationProfileRow,
	type GasketItemOption,
	type GlazingAutoChannel,
	type GlazingAutoConfig,
	type GlobalGlazingProfileType,
	type GlobalGlazingRule,
	type ProfileSeriesRow,
	type SectionRuleHost,
	type SectionSide,
} from '@/studio/api'
import {
	defaultGlazingAutoConfig,
	extractGasketCatalog,
	normalizeGlazingAutoConfig,
	resolveGlazingByWidth,
} from '@/studio/glazingSolver'

type AccordionKey = 'window' | 'door'
type PreviewContextKey = 'window_frame' | 'window_sash' | 'door_frame' | 'door_sash'

const route = useRoute()

const loading = ref(true)
const saving = ref(false)
const dirty = ref(false)
const error = ref('')
const editingKey = ref<string | null>(null)
const openAccordions = reactive<Record<AccordionKey, boolean>>({
	window: true,
	door: true,
})

const rules = ref<GlobalGlazingRule[]>([])
const autoConfig = ref<GlazingAutoConfig>(defaultGlazingAutoConfig())
const seriesList = ref<ProfileSeriesRow[]>([])
const selectedSeries = ref<string>('')
const previewContext = ref<PreviewContextKey>('window_frame')
const customProbeThickness = ref<string>('')

const beads = ref<FenestrationProfileRow[]>([])
const hardware = ref<FenestrationHardwareRow[]>([])
const gasketItems = ref<GasketItemOption[]>([])
const glasses = ref<FenestrationGlassRow[]>([])

const previewContexts: Array<{
	key: PreviewContextKey
	label: string
	application: GlobalGlazingProfileType
	host: SectionRuleHost
}> = [
	{ key: 'window_frame', label: 'Window Frame', application: 'window', host: 'frame' },
	{ key: 'window_sash', label: 'Window Sash', application: 'window', host: 'sash' },
	{ key: 'door_frame', label: 'Door Frame', application: 'door', host: 'frame' },
	{ key: 'door_sash', label: 'Door Sash', application: 'door', host: 'sash' },
]

interface BeadOption {
	code: string
	label: string
	series?: string
	svg?: string | null
	w: number
	d: number
}

const beadOptions = computed<BeadOption[]>(() => {
	const map = new Map<string, BeadOption>()
	for (const hw of hardware.value) {
		if (hw.category !== 'Beading') continue
		const code = hw.hardware_code || hw.name
		map.set(code, {
			code,
			label: hw.hardware_name || code,
			svg: hw.section_svg,
			w: Number(hw.width_mm || 25),
			d: Number(hw.depth_mm || 25),
		})
	}
	for (const p of beads.value) {
		const rawCode = p.profile_code || p.name
		const baseCode = rawCode.includes('-') ? rawCode.split('-')[0] : rawCode
		if (!map.has(baseCode)) {
			map.set(baseCode, {
				code: baseCode,
				label: (p.profile_name || baseCode).replace(/\s*\(CS\d+\)\s*$/i, '').trim(),
				series: p.series,
				svg: p.section_svg,
				w: Number(p.width_mm || 25),
				d: Number(p.depth_mm || 25),
			})
		}
	}
	return [...map.values()].sort((a, b) => a.code.localeCompare(b.code))
})

const seriesSpecificBeadOptions = computed<BeadOption[]>(() => {
	if (!selectedSeries.value) return []
	const target = selectedSeries.value.toLowerCase()
	return beads.value
		.filter((p) => String(p.series || '').toLowerCase() === target)
		.map((p) => {
			const code = p.profile_code || p.name
			return {
				code,
				label: p.profile_name || code,
				series: p.series,
				svg: p.section_svg,
				w: Number(p.width_mm || 25),
				d: Number(p.depth_mm || 25),
			}
		})
})

interface GasketOption {
	value: string
	itemCode: string
	name: string
	thickness?: number | null
	label: string
	svg?: string | null
	w: number
	d: number
}

const gasketOptions = computed<GasketOption[]>(() => {
	const hwGaskets = hardware.value.filter((hw) => hw.category === 'Gasket' || hw.category === 'Seal / Weatherstrip')
	if (hwGaskets.length) {
		return hwGaskets.map((hw) => {
			const code = hw.hardware_code || hw.name
			const thk = hw.thickness_mm ? ` (${hw.thickness_mm} mm)` : ''
			return {
				value: code,
				itemCode: hw.item || code,
				name: hw.hardware_name || code,
				thickness: hw.thickness_mm,
				label: `${code} · ${hw.hardware_name}${thk}`,
				svg: hw.section_svg,
				w: Number(hw.width_mm || 10),
				d: Number(hw.depth_mm || 10),
			}
		})
	}
	return gasketItems.value.map((item) => ({
		value: item.name,
		itemCode: item.name,
		name: item.item_name || item.name,
		thickness: null,
		label: item.item_name ? `${item.name} · ${item.item_name}` : item.name,
		svg: null,
		w: 10,
		d: 10,
	}))
})

const sizedGaskets = computed(() => extractGasketCatalog(hardware.value, []))

function isGasketInPool(code: string): boolean {
	const pool = autoConfig.value.gasket_pool
	if (!pool.length) return true
	return pool.some((c) => c.toLowerCase() === code.toLowerCase())
}

function toggleGasketInPool(code: string) {
	const allCodes = sizedGaskets.value.map((g) => g.code)
	const current = autoConfig.value.gasket_pool.length ? [...autoConfig.value.gasket_pool] : [...allCodes]
	const idx = current.findIndex((c) => c.toLowerCase() === code.toLowerCase())
	if (idx >= 0) {
		if (current.length <= 1) return
		current.splice(idx, 1)
	} else {
		current.push(code)
	}
	autoConfig.value.gasket_pool = current.length === allCodes.length ? [] : current
	dirty.value = true
}

function channelCountForSeries(series: string): number {
	const target = (series || '').trim().toLowerCase()
	return autoConfig.value.channels.filter((ch) => (ch.series || '').trim().toLowerCase() === target).length
}

const activeSeriesChannels = computed<GlazingAutoChannel[]>(() => {
	const target = selectedSeries.value.trim().toLowerCase()
	return autoConfig.value.channels.filter((ch) => (ch.series || '').trim().toLowerCase() === target)
})

const hasEffectiveAutoChannels = computed(() => {
	if (!autoConfig.value.enabled) return false
	return activeSeriesChannels.value.length > 0 || channelCountForSeries('') > 0
})

function addAutoChannel(noBead: boolean) {
	const defaultBead = noBead
		? ''
		: seriesSpecificBeadOptions.value[0]?.code || beadOptions.value[0]?.code || ''
	const existingWidths = activeSeriesChannels.value.map((c) => Number(c.bead_width_mm || 0))
	const defaultBw = noBead
		? 28
		: existingWidths.length
			? Math.round((Math.max(...existingWidths) + 6) * 100) / 100
			: 12.01
	autoConfig.value.channels.push({
		id: `glazing_ch_${Date.now()}_${autoConfig.value.channels.length + 1}`,
		series: selectedSeries.value,
		label: noBead ? 'Sash Pocket (No Bead)' : '',
		profile_type: 'both',
		host: noBead ? 'sash' : 'frame',
		bead_profile: defaultBead,
		no_bead: noBead || !defaultBead,
		bead_width_mm: defaultBw,
		bead_side: 'inside',
	})
	dirty.value = true
}

function onAutoChannelBeadChange(ch: GlazingAutoChannel, value: string) {
	ch.bead_profile = value
	ch.no_bead = !value
	dirty.value = true
}

function removeAutoChannel(ch: GlazingAutoChannel) {
	const idx = autoConfig.value.channels.indexOf(ch)
	if (idx === -1) return
	autoConfig.value.channels.splice(idx, 1)
	dirty.value = true
}

const activePreviewMeta = computed(
	() => previewContexts.find((c) => c.key === previewContext.value) ?? previewContexts[0],
)

const previewRows = computed(() => {
	const ctx = activePreviewMeta.value
	const items: Array<{ key: string; thickness: number; label: string }> = []
	const customVal = Number(customProbeThickness.value)
	if (customProbeThickness.value !== '' && Number.isFinite(customVal) && customVal > 0) {
		items.push({ key: `probe-${customVal}`, thickness: customVal, label: 'Custom test' })
	}
	const seenThk = new Set<string>()
	for (const g of glasses.value) {
		const t = Number(g.thickness_mm || 0)
		if (!(t > 0)) continue
		const code = g.glass_code || g.name
		const key = `${code}-${t}`
		if (seenThk.has(key)) continue
		seenThk.add(key)
		items.push({ key, thickness: t, label: code })
	}
	if (!items.length) {
		for (const t of [5, 6, 8, 12, 13, 15, 24]) {
			items.push({ key: `std-${t}`, thickness: t, label: 'Standard' })
		}
	}
	return items.map((item) => ({
		...item,
		res: resolveGlazingByWidth(
			autoConfig.value,
			hardware.value,
			item.thickness,
			selectedSeries.value,
			ctx.host,
			ctx.application,
		),
	}))
})

const accordionSections = computed<
	Array<{ key: AccordionKey; title: string; subtitle: string; rules: GlobalGlazingRule[] }>
>(() => [
	{
		key: 'window',
		title: 'Window',
		subtitle: 'Rules for Window frames & sashes (includes shared Door & Window rules)',
		rules: rules.value.filter((r) => (r.profile_type || 'both') === 'window' || (r.profile_type || 'both') === 'both'),
	},
	{
		key: 'door',
		title: 'Door',
		subtitle: 'Rules for Door frames & sashes (includes shared Door & Window rules)',
		rules: rules.value.filter((r) => (r.profile_type || 'both') === 'door' || (r.profile_type || 'both') === 'both'),
	},
])

function toggleAccordion(key: AccordionKey) {
	openAccordions[key] = !openAccordions[key]
}

function isNoBead(rule: GlobalGlazingRule): boolean {
	return Boolean(rule.no_bead) || !String(rule.bead_profile || '').trim()
}

function isEditing(secKey: AccordionKey, rule: GlobalGlazingRule): boolean {
	return editingKey.value === `${secKey}:${rule.id}`
}

function toggleEdit(secKey: AccordionKey, rule: GlobalGlazingRule) {
	const key = `${secKey}:${rule.id}`
	editingKey.value = editingKey.value === key ? null : key
}

function beadShortName(code: string): string {
	if (!code) return 'None'
	const base = code.includes('-') ? code.split('-')[0] : code
	return (
		seriesSpecificBeadOptions.value.find((b) => b.code === code)?.label ||
		beadOptions.value.find((b) => b.code === code || b.code === base)?.label ||
		code
	)
}

function gasketSubLabel(code: string): string {
	if (!code) return 'Not assigned'
	const g = gasketOptions.value.find((x) => x.value === code || x.itemCode === code)
	if (g?.thickness) return `${g.thickness} mm gasket`
	return g?.name || code
}

function hostLabel(host: SectionRuleHost): string {
	if (host === 'frame') return 'Frame'
	if (host === 'sash') return 'Sash'
	return 'Frame & Sash'
}

function beadSvgFor(code: string): string | null {
	if (!code) return null
	const base = code.includes('-') ? code.split('-')[0] : code
	return (
		seriesSpecificBeadOptions.value.find((b) => b.code === code)?.svg ??
		beadOptions.value.find((b) => b.code === code || b.code === base)?.svg ??
		null
	)
}

function beadViewBoxFor(code: string): string {
	const base = code.includes('-') ? code.split('-')[0] : code
	const b =
		seriesSpecificBeadOptions.value.find((x) => x.code === code) ??
		beadOptions.value.find((x) => x.code === code || x.code === base)
	const w = Math.max(8, b?.w || 25)
	const d = Math.max(8, b?.d || 25)
	return `-2 -2 ${w + 4} ${d + 4}`
}

function gasketSvgFor(code: string): string | null {
	if (!code) return null
	return gasketOptions.value.find((g) => g.value === code || g.itemCode === code)?.svg ?? null
}

function gasketViewBoxFor(code: string): string {
	const g = gasketOptions.value.find((x) => x.value === code || x.itemCode === code)
	const w = Math.max(4, g?.w || 10)
	const d = Math.max(4, g?.d || 10)
	return `-1 -1 ${w + 2} ${d + 2}`
}

function matchingGlasses(rule: GlobalGlazingRule): FenestrationGlassRow[] {
	const minG = Number(rule.min_glass_mm || 0)
	const maxG = Number(rule.max_glass_mm || 0)
	return glasses.value.filter((g) => {
		const t = Number(g.thickness_mm || 0)
		return t >= minG - 1e-6 && t <= maxG + 1e-6
	})
}

const coveredGlassNames = computed(() => {
	const matched = new Set<string>()
	for (const r of rules.value) {
		for (const g of matchingGlasses(r)) matched.add(g.name)
	}
	return matched
})

const coveredGlassCount = computed(() => coveredGlassNames.value.size)

const uncoveredGlasses = computed(() => glasses.value.filter((g) => !coveredGlassNames.value.has(g.name)))

function setBeadSide(rule: GlobalGlazingRule, side: SectionSide) {
	if (rule.bead_side === side) return
	rule.bead_side = side
	dirty.value = true
}

function onBeadProfileChange(rule: GlobalGlazingRule, value: string) {
	rule.bead_profile = value
	rule.no_bead = !value
	dirty.value = true
}

function onProfileTypeChange(rule: GlobalGlazingRule, nextType: GlobalGlazingProfileType, currentSection: AccordionKey) {
	rule.profile_type = nextType
	if (nextType === 'window' && currentSection !== 'window') {
		openAccordions.window = true
		editingKey.value = `window:${rule.id}`
	} else if (nextType === 'door' && currentSection !== 'door') {
		openAccordions.door = true
		editingKey.value = `door:${rule.id}`
	}
	dirty.value = true
}

function onSelectGasket(rule: GlobalGlazingRule, which: 'inner' | 'outer', value: string) {
	const opt = gasketOptions.value.find((g) => g.value === value)
	if (which === 'inner') {
		rule.inner_gasket_hardware = value
		rule.inner_gasket_item = opt?.itemCode || value
		rule.inner_gasket_name = opt?.name || value
	} else {
		rule.outer_gasket_hardware = value
		rule.outer_gasket_item = opt?.itemCode || value
		rule.outer_gasket_name = opt?.name || value
	}
	dirty.value = true
}

function addRule(profileType: GlobalGlazingProfileType = 'both') {
	const lastMax = rules.value.length ? Number(rules.value[rules.value.length - 1].max_glass_mm || 6) : 5
	const id = `global_rule_${Date.now()}_${rules.value.length + 1}`
	const firstBead = beadOptions.value[0]?.code || ''
	rules.value.push({
		id,
		label: '',
		profile_type: profileType,
		min_glass_mm: rules.value.length ? Math.round((lastMax + 0.5) * 10) / 10 : 5,
		max_glass_mm: rules.value.length ? Math.round((lastMax + 4) * 10) / 10 : 5.5,
		host: 'frame',
		bead_profile: firstBead,
		no_bead: !firstBead,
		bead_side: 'inside',
		inner_gasket_hardware: '',
		inner_gasket_item: '',
		inner_gasket_name: '',
		outer_gasket_hardware: '',
		outer_gasket_item: '',
		outer_gasket_name: '',
	})
	const targetSection: AccordionKey = profileType === 'door' ? 'door' : 'window'
	openAccordions[targetSection] = true
	editingKey.value = `${targetSection}:${id}`
	dirty.value = true
}

function addRuleForThickness(thickness: number) {
	const t = Math.round(Number(thickness || 6) * 100) / 100
	const id = `global_rule_${Date.now()}_${rules.value.length + 1}`
	const firstBead = beadOptions.value[0]?.code || ''
	rules.value.push({
		id,
		label: `${t} mm Glass`,
		profile_type: 'both',
		min_glass_mm: Math.max(0, Math.floor(t * 2) / 2),
		max_glass_mm: Math.ceil(t * 2) / 2,
		host: 'frame',
		bead_profile: firstBead,
		no_bead: !firstBead,
		bead_side: 'inside',
		inner_gasket_hardware: gasketOptions.value[0]?.value || '',
		inner_gasket_item: gasketOptions.value[0]?.itemCode || '',
		inner_gasket_name: gasketOptions.value[0]?.name || '',
		outer_gasket_hardware: gasketOptions.value[0]?.value || '',
		outer_gasket_item: gasketOptions.value[0]?.itemCode || '',
		outer_gasket_name: gasketOptions.value[0]?.name || '',
	})
	openAccordions.window = true
	editingKey.value = `window:${id}`
	dirty.value = true
}

function autoFillStandardRanges() {
	const pickBead = (hint: string) =>
		beadOptions.value.find((b) => `${b.code} ${b.label}`.toLowerCase().includes(hint))?.code ||
		beadOptions.value[0]?.code ||
		''
	const pickGasket = (hint: string) =>
		gasketOptions.value.find((g) => `${g.value} ${g.label}`.toLowerCase().includes(hint))

	const g2 = pickGasket('g22') || pickGasket('2mm')
	const g3 = pickGasket('g23') || pickGasket('3mm')
	const g4 = pickGasket('g24') || pickGasket('4mm')
	const g5 = pickGasket('g25') || pickGasket('5mm')

	const makeRow = (
		id: string,
		label: string,
		profileType: GlobalGlazingProfileType,
		host: SectionRuleHost,
		min: number,
		max: number,
		bead: string,
		inner?: GasketOption,
		outer?: GasketOption,
	): GlobalGlazingRule => ({
		id,
		label,
		profile_type: profileType,
		min_glass_mm: min,
		max_glass_mm: max,
		host,
		bead_profile: bead,
		no_bead: !bead,
		bead_side: 'inside',
		inner_gasket_hardware: inner?.value || '',
		inner_gasket_item: inner?.itemCode || '',
		inner_gasket_name: inner?.name || '',
		outer_gasket_hardware: outer?.value || '',
		outer_gasket_item: outer?.itemCode || '',
		outer_gasket_name: outer?.name || '',
	})

	rules.value = [
		makeRow('std_5mm', '5 mm Glass', 'both', 'frame', 4.5, 5.5, pickBead('e104161') || pickBead('5mm'), g3 || g2, g4 || g5),
		makeRow('std_6_8mm', '6–8 mm Glass', 'both', 'frame', 6, 8.5, pickBead('cs4807') || pickBead('6'), g3 || g2, g4 || g3),
		makeRow('std_10_18mm', '10–18 mm Glass / Lami', 'both', 'frame', 9.5, 18, pickBead('cs4808') || pickBead('12'), g2 || g3, g3 || g2),
		makeRow('std_24mm', '20–26 mm DGU', 'both', 'frame', 19, 26, pickBead('cs4809') || pickBead('24'), g2 || g3, g2 || g3),
	]
	editingKey.value = null
	dirty.value = true
}

function removeRule(rule: GlobalGlazingRule) {
	const idx = rules.value.indexOf(rule)
	if (idx === -1) return
	if (editingKey.value?.endsWith(`:${rule.id}`)) editingKey.value = null
	rules.value.splice(idx, 1)
	dirty.value = true
}

function normalizeLoadedRule(r: GlobalGlazingRule, idx: number): GlobalGlazingRule {
	const noBead = Boolean(r.no_bead) || !String(r.bead_profile || '').trim()
	return {
		...r,
		id: r.id || `global_rule_${idx + 1}`,
		profile_type:
			r.profile_type === 'window' || r.profile_type === 'door' || r.profile_type === 'both'
				? r.profile_type
				: 'both',
		bead_profile: noBead ? '' : String(r.bead_profile || '').trim(),
		no_bead: noBead,
	}
}

async function load() {
	loading.value = true
	error.value = ''
	try {
		const res = await getGlobalGlazingRules()
		rules.value = (res.rules ?? []).map(normalizeLoadedRule)
		autoConfig.value = normalizeGlazingAutoConfig(res.auto_config)
		seriesList.value = res.series_list ?? []
		beads.value = res.beads ?? []
		hardware.value = res.hardware ?? []
		gasketItems.value = res.gasket_items ?? []
		glasses.value = res.glasses ?? []

		const querySeries = String(route.query.series || '').trim()
		if (querySeries && seriesList.value.some((s) => (s.series_code || s.name) === querySeries)) {
			selectedSeries.value = querySeries
		} else if (seriesList.value.length && !selectedSeries.value) {
			const withChannels = seriesList.value.find((s) => channelCountForSeries(s.series_code || s.name) > 0)
			selectedSeries.value = withChannels
				? withChannels.series_code || withChannels.name
				: seriesList.value[0].series_code || seriesList.value[0].name
		}
		dirty.value = false
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Could not load bead & gasket configuration'
	} finally {
		loading.value = false
	}
}

async function save() {
	saving.value = true
	error.value = ''
	try {
		const payload = rules.value.map((r) => ({
			...r,
			profile_type: r.profile_type || 'both',
			bead_profile: isNoBead(r) ? '' : r.bead_profile,
			no_bead: isNoBead(r),
		}))
		const normalizedAuto = normalizeGlazingAutoConfig(autoConfig.value)
		const res = await saveGlobalGlazingRules(payload, normalizedAuto)
		rules.value = (res.rules ?? payload).map(normalizeLoadedRule)
		if (res.auto_config) {
			autoConfig.value = normalizeGlazingAutoConfig(res.auto_config)
		}
		editingKey.value = null
		dirty.value = false
		toast.success('Bead & Gasket Configuration saved')
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Could not save bead & gasket configuration'
		toast.error(error.value)
	} finally {
		saving.value = false
	}
}

onMounted(load)
</script>
