<template>
	<div class="mx-auto max-w-4xl p-6">
		<div class="mb-4 flex items-center gap-3">
			<h1 class="text-xl font-semibold">Projects</h1>
			<FormControl v-model="search" type="search" placeholder="Search projects" class="ml-auto w-64" />
			<Button variant="solid" @click="showNew = true">New project</Button>
		</div>

		<ul class="divide-y rounded border">
			<li v-for="p in filtered" :key="p.name">
				<RouterLink :to="`/projects/${p.name}`" class="flex min-h-[44px] items-center gap-3 px-4 py-2 hover:bg-surface-gray-1">
					<span class="font-medium">{{ p.project_title || p.name }}</span>
					<span class="text-sm text-ink-gray-5">{{ p.customer }}</span>
					<span class="ml-auto text-sm text-ink-gray-5">{{ p.name }}</span>
				</RouterLink>
			</li>
			<li v-if="!filtered.length" class="px-4 py-6 text-center text-sm text-ink-gray-5">No projects found.</li>
		</ul>

		<Dialog v-model="showNew" title="New project">
			<div class="space-y-3">
				<FormControl v-model="form.project_title" label="Title" />
				<FormControl v-model="form.customer" label="Customer (optional)" />
				<FormControl
					v-model="form.default_series_version"
					type="select"
					label="Default series version"
					:options="versionOptions"
				/>
				<Alert v-if="error" theme="red" :title="error" />
			</div>
			<template #actions>
				<Button variant="solid" :loading="saving" :disabled="!canCreate" @click="create">Create project</Button>
			</template>
		</Dialog>
	</div>
</template>

<script setup lang="ts">
import { Alert, Button, Dialog, FormControl, useList } from 'frappe-ui'
import { computed, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { createProject } from '@/api'

interface ProjectRow {
	name: string
	project_title: string
	customer: string
	modified: string
}

const router = useRouter()
const search = ref('')
const showNew = ref(false)
const saving = ref(false)
const error = ref('')
const form = reactive({ project_title: '', customer: '', default_series_version: '' })

const projects = useList<ProjectRow>({
	doctype: 'Fenestration Project',
	fields: ['name', 'project_title', 'customer', 'modified'],
	orderBy: 'modified desc',
	limit: 100,
})
const versions = useList<{ name: string }>({
	doctype: 'Series Version',
	fields: ['name'],
	filters: { docstatus: 1 },
	limit: 100,
})

const filtered = computed(() => {
	const q = search.value.trim().toLowerCase()
	const rows = projects.data ?? []
	if (!q) return rows
	return rows.filter((p) => [p.name, p.project_title, p.customer].some((v) => (v ?? '').toLowerCase().includes(q)))
})
const versionOptions = computed(() => (versions.data ?? []).map((v) => ({ label: v.name, value: v.name })))
const canCreate = computed(() => !!form.project_title.trim() && !!form.default_series_version)

async function create() {
	saving.value = true
	error.value = ''
	try {
		const name = await createProject({
			project_title: form.project_title.trim(),
			customer: form.customer.trim() || undefined,
			default_series_version: form.default_series_version,
		})
		showNew.value = false
		router.push(`/projects/${name}`)
	} catch (e) {
		error.value = e instanceof Error ? e.message : 'Could not create the project.'
	} finally {
		saving.value = false
	}
}
</script>
