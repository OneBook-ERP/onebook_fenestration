<template>
	<div class="mx-auto max-w-4xl p-6">
		<header class="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-outline-gray-2 pb-4">
			<div>
				<nav aria-label="Breadcrumb" class="mb-1 flex items-center gap-1.5 text-sm text-ink-gray-5">
					<router-link to="/series-studio?tab=glass" class="hover:text-ink-gray-8">
						Series Studio
					</router-link>
					<span aria-hidden="true">/</span>
					<router-link to="/series-studio?tab=glass" class="hover:text-ink-gray-8">
						Fenestration Glass
					</router-link>
					<span aria-hidden="true">/</span>
					<span class="font-medium text-ink-gray-8">{{ isEdit ? form.glass_code : 'New Fenestration Glass' }}</span>
				</nav>
				<div class="flex flex-wrap items-center gap-3">
					<h1 class="text-xl font-semibold text-ink-gray-9">
						{{ isEdit ? `${form.glass_code} · ${form.glass_name || 'Glass'}` : (form.glass_name || 'New Fenestration Glass') }}
					</h1>
					<Badge v-if="form.thickness_mm" theme="blue" :label="`${form.thickness_mm} mm`" />
				</div>
			</div>

			<div class="flex items-center gap-2.5">
				<Button variant="outline" label="Back to Glass" route="/series-studio?tab=glass" />
				<Button
					variant="solid"
					:label="isEdit ? 'Save Changes' : 'Create Glass'"
					:loading="saving"
					:disabled="!canSave"
					data-testid="save-glass-btn"
					@click="save"
				/>
			</div>
		</header>

		<div v-if="loadingDoc" class="py-12 text-center text-sm text-ink-gray-5">
			Loading glass specification…
		</div>

		<div v-else class="space-y-8">
			<Alert v-if="error" theme="red" :title="error" />

			<section>
				<h2 class="mb-4 text-base font-semibold text-ink-gray-9">Glass Specification</h2>
				<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
					<div class="space-y-4">
						<FormControl
							v-model="form.glass_code"
							label="Glass Code *"
							placeholder="e.g. CLEAR-5 or TOUGH-6"
							:disabled="isEdit"
						/>
						<FormControl
							v-model="form.glass_name"
							label="Glass Name *"
							placeholder="e.g. 5mm Clear Float Glass"
						/>
					</div>

					<div class="space-y-4">
						<FormControl
							v-model.number="form.thickness_mm"
							type="number"
							step="0.5"
							label="Thickness (mm) *"
							placeholder="5"
						/>
						<Combobox
							v-model="form.item"
							label="Item"
							placeholder="Search or select ERPNext Item..."
							:options="itemOptions"
						/>
					</div>
				</div>
			</section>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Alert, Badge, Button, Combobox, FormControl, toast, useList } from 'frappe-ui'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getFenestrationGlassDoc, saveFenestrationGlass } from '@/studio/api'

const props = defineProps<{ name?: string }>()
const router = useRouter()

const isEdit = computed(() => Boolean(props.name))
const loadingDoc = ref(false)
const saving = ref(false)
const error = ref('')

const form = reactive({
	glass_code: '',
	glass_name: '',
	thickness_mm: 5,
	item: '',
})

const itemsResource = useList<{ name: string; item_name?: string }>({
	doctype: 'Item',
	fields: ['name', 'item_name'],
	limit: 500,
})

const itemOptions = computed(() =>
	(itemsResource.data ?? []).map((i) => ({
		label: i.item_name ? `${i.name} — ${i.item_name}` : i.name,
		value: i.name,
	})),
)

const canSave = computed(() =>
	Boolean(
		form.glass_code.trim() &&
			form.glass_name.trim() &&
			Number(form.thickness_mm) > 0 &&
			!saving.value,
	),
)

onMounted(async () => {
	if (!props.name) return
	loadingDoc.value = true
	try {
		const doc = await getFenestrationGlassDoc(props.name)
		form.glass_code = doc.glass_code || doc.name
		form.glass_name = doc.glass_name || ''
		form.thickness_mm = Number(doc.thickness_mm || 5)
		form.item = doc.item || ''
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Could not load glass specification'
	} finally {
		loadingDoc.value = false
	}
})

async function save() {
	if (!canSave.value) return
	saving.value = true
	error.value = ''
	try {
		const savedName = await saveFenestrationGlass(
			{
				glass_code: form.glass_code.trim(),
				glass_name: form.glass_name.trim(),
				thickness_mm: Number(form.thickness_mm),
				item: form.item.trim() || null,
			},
			props.name || null,
		)
		toast.success(isEdit.value ? 'Glass specification updated' : 'Glass specification created')
		if (!isEdit.value) {
			router.replace(`/series-studio/glass/${encodeURIComponent(savedName)}`)
		}
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Could not save glass specification'
	} finally {
		saving.value = false
	}
}
</script>

