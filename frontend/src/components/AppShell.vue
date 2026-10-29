<template>
	<div class="flex h-screen w-screen bg-surface-white text-ink-gray-8">
		<SidebarRail>
			<SidebarRailItem label="Fenestration" variant="ghost" icon="lucide-layout-grid" route="/projects" />
			<div class="flex w-full flex-1 flex-col items-center gap-3 overflow-y-auto pt-3">
				<SidebarRailItem
					v-for="m in modules"
					:key="m.label"
					:label="m.label"
					:icon="m.icon"
					:route="m.route"
					:description="m.route ? undefined : 'Soon'"
					:disabled="!m.route"
					:aria-disabled="!m.route"
					:active="m.label === 'Projects'"
				/>
				<SidebarRailItem
					v-if="isEngineer"
					label="Series Studio"
					icon="lucide-layers"
					href="/app/profile-series"
				/>
			</div>
			<Dropdown :options="userMenu" side="right" align="end">
				<SidebarRailItem label="Account" variant="ghost">
					<Avatar :label="user" size="md" />
				</SidebarRailItem>
			</Dropdown>
		</SidebarRail>

		<Sidebar v-model:collapsed="collapsed" aria-label="Projects">
			<SidebarHeader title="Projects" :show-logo="false" />
			<div class="flex-1 overflow-y-auto">
				<SidebarItem label="All projects" icon="lucide-folder-kanban" route="/projects" />
				<SidebarSection label="Recent projects">
					<SidebarItem
						v-for="p in recent"
						:key="p.name"
						:label="p.project_title || p.name"
						:route="`/projects/${p.name}`"
					/>
				</SidebarSection>
			</div>
			<SidebarCollapseToggle />
		</Sidebar>

		<main class="min-w-0 flex-1 overflow-y-auto">
			<slot />
		</main>
	</div>
</template>

<script setup lang="ts">
import {
	Avatar,
	Dropdown,
	Sidebar,
	SidebarCollapseToggle,
	SidebarHeader,
	SidebarItem,
	SidebarRail,
	SidebarRailItem,
	SidebarSection,
	useList,
} from 'frappe-ui'
import { computed, ref } from 'vue'
import { logout } from '@/api'

const props = defineProps<{ user: string; roles: string[] }>()

interface RecentProject {
	name: string
	project_title: string
}

const modules = [
	{ label: 'Projects', icon: 'lucide-folder-kanban', route: '/projects' },
	{ label: 'Production', icon: 'lucide-factory' },
	{ label: 'Install', icon: 'lucide-wrench' },
	{ label: 'Orders', icon: 'lucide-package' },
]

const isEngineer = computed(() => props.roles.some((r) => r === 'System Manager' || r === 'Fenestration Engineer'))
const collapsed = ref(typeof window !== 'undefined' && window.innerWidth < 768)

const projects = useList<RecentProject>({
	doctype: 'Fenestration Project',
	fields: ['name', 'project_title', 'modified'],
	orderBy: 'modified desc',
	limit: 5,
})
const recent = computed(() => (projects.data ?? []).slice(0, 5))

const userMenu = [
	{ label: 'Open Desk', icon: 'lucide-layout-dashboard', onClick: () => (window.location.href = '/app') },
	{
		label: 'Log out',
		icon: 'lucide-log-out',
		onClick: async () => {
			await logout()
			window.location.href = '/login'
		},
	},
]
</script>
