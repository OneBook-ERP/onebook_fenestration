<template>
	<div class="relative flex h-screen w-screen overflow-hidden bg-surface-white text-ink-gray-8">
		<!-- Left Icon Rail (ERPNext-style) -->
		<aside
			aria-label="Primary navigation"
			class="z-30 flex h-full w-[48px] shrink-0 flex-col items-center border-r border-outline-gray-1 bg-surface-sidebar px-1.5 pb-3 pt-2.5"
		>
			<TooltipProvider :hover-delay="0">
				<!-- Brand Mark -->
				<Tooltip text="Fenestration" side="right">
					<RouterLink
						to="/projects"
						aria-label="Fenestration"
						class="mb-2.5 flex size-7 shrink-0 items-center justify-center rounded-[7px] bg-[#0070f3] text-white shadow-sm transition-transform duration-150 hover:scale-[1.04] active:scale-[0.97]"
					>
						<svg class="size-4" viewBox="0 0 20 20" fill="none" aria-hidden="true">
							<rect x="2.5" y="2.5" width="15" height="15" rx="2" stroke="currentColor" stroke-width="1.8" />
							<line x1="10" y1="2.5" x2="10" y2="17.5" stroke="currentColor" stroke-width="1.6" />
							<line x1="2.5" y1="10" x2="17.5" y2="10" stroke="currentColor" stroke-width="1.6" />
						</svg>
					</RouterLink>
				</Tooltip>

				<!-- Quick Search Trigger -->
				<Tooltip text="Search (⌘K)" side="right">
					<button
						type="button"
						aria-label="Search"
						class="mb-3 flex size-8 shrink-0 items-center justify-center rounded-[7px] text-ink-gray-6 transition-colors duration-150 hover:bg-surface-gray-2 hover:text-ink-gray-8"
						@click="searchOpen = true"
					>
						<span class="lucide-search size-4" />
					</button>
				</Tooltip>

				<!-- Module Rail Items -->
				<div class="flex w-full flex-1 flex-col items-center gap-1 overflow-y-auto py-0.5">
					<Tooltip
						v-for="m in railModules"
						:key="m.key"
						:text="m.label"
						side="right"
					>
						<button
							type="button"
							:aria-label="m.label"
							:aria-current="m.active ? 'page' : undefined"
							class="flex size-8 shrink-0 items-center justify-center rounded-[7px] transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
							:class="
								m.active
									? 'bg-white text-ink-gray-8 shadow-[0_1px_2px_rgba(0,0,0,0.08)]'
									: 'text-ink-gray-6 hover:bg-surface-gray-2 hover:text-ink-gray-8'
							"
							@click="onRailClick(m)"
						>
							<span :class="[m.icon, 'size-4']" />
						</button>
					</Tooltip>
				</div>

				<!-- Expand Sidebar Trigger (shown when secondary panel is collapsed) -->
				<Tooltip v-if="collapsed" text="Expand sidebar (⌘B)" side="right">
					<button
						type="button"
						aria-label="Expand sidebar"
						class="mb-2 flex size-8 shrink-0 items-center justify-center rounded-[7px] text-ink-gray-6 transition-colors duration-150 hover:bg-surface-gray-2 hover:text-ink-gray-8"
						@click="collapsed = false"
					>
						<span class="lucide-panel-left-open size-4" />
					</button>
				</Tooltip>

				<!-- User Account Avatar -->
				<Dropdown :options="userMenu" side="right" align="end">
					<button
						type="button"
						aria-label="Account"
						class="flex size-7 shrink-0 items-center justify-center rounded-full bg-[#e6f4ea] text-[12px] font-semibold text-[#137333] transition-transform duration-150 hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
					>
						{{ userInitial }}
					</button>
				</Dropdown>
			</TooltipProvider>
		</aside>

		<!-- Mobile Backdrop when secondary sidebar is open -->
		<Transition
			enter-active-class="transition-opacity duration-200 ease-out"
			enter-from-class="opacity-0"
			enter-to-class="opacity-100"
			leave-active-class="transition-opacity duration-150 ease-in"
			leave-from-class="opacity-100"
			leave-to-class="opacity-0"
		>
			<div
				v-if="!collapsed"
				class="fixed inset-y-0 left-[48px] right-0 z-20 bg-black/20 md:hidden"
				aria-hidden="true"
				@click="collapsed = true"
			/>
		</Transition>

		<!-- Secondary Sidebar Panel -->
		<nav
			data-slot="sidebar"
			:data-state="collapsed ? 'collapsed' : 'expanded'"
			:aria-label="moduleTitle"
			class="fixed inset-y-0 left-[48px] z-30 flex h-full shrink-0 flex-col overflow-hidden bg-surface-sidebar transition-[width] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] md:static"
			:class="collapsed ? 'w-0 border-r-0' : 'w-[224px] border-r border-outline-gray-1 shadow-xl md:shadow-none'"
		>
			<div
				class="flex h-full w-[224px] flex-col transition-[opacity,transform] duration-250 ease-[cubic-bezier(0.4,0,0.2,1)]"
				:class="collapsed ? 'pointer-events-none -translate-x-2 opacity-0' : 'translate-x-0 opacity-100'"
			>
				<!-- Panel Header with Module Switcher & Collapse Button -->
				<div class="flex h-12 shrink-0 items-center justify-between gap-1 px-2">
					<Dropdown :options="moduleMenu" match-trigger-width class="min-w-0 flex-1">
						<button
							type="button"
							data-slot="sidebar-module-switcher"
							class="flex h-8 w-full min-w-0 items-center justify-between gap-1.5 rounded-[7px] px-2 text-left text-[14px] font-medium text-ink-gray-8 transition-colors duration-150 hover:bg-surface-gray-2"
						>
							<span class="truncate">{{ moduleTitle }}</span>
							<span class="lucide-chevron-down size-3.5 shrink-0 text-ink-gray-5" />
						</button>
					</Dropdown>

					<button
						type="button"
						aria-label="Collapse sidebar"
						title="Collapse sidebar (⌘B)"
						class="flex size-7 shrink-0 items-center justify-center rounded-[7px] text-ink-gray-4 transition-colors duration-150 hover:bg-surface-gray-2 hover:text-ink-gray-7"
						@click="collapsed = true"
					>
						<span class="lucide-panel-left-close size-4" />
					</button>
				</div>

				<!-- Panel Navigation Body -->
				<div class="flex-1 overflow-y-auto px-2 pb-4 pt-0.5">
					<Transition
						mode="out-in"
						enter-active-class="transition duration-150 ease-out"
						enter-from-class="opacity-0 translate-y-1"
						enter-to-class="opacity-100 translate-y-0"
						leave-active-class="transition duration-100 ease-in"
						leave-from-class="opacity-100 translate-y-0"
						leave-to-class="opacity-0 -translate-y-1"
					>
						<!-- Series Studio -->
						<div v-if="activeModule === 'studio'" key="studio" class="flex flex-col gap-0.5">
							<SidebarItem
								v-for="item in studioItems"
								:key="item.tab"
								:label="item.label"
								:icon="item.icon"
								:active="activeStudioTab === item.tab"
								:route="item.route"
								class="!h-[30px] !rounded-[7px]"
							/>

							<div class="mt-1.5">
								<SidebarNavGroup label="Quick create" icon="lucide-plus-circle" :default-open="false">
									<SidebarItem
										v-for="item in studioCreateItems"
										:key="item.route"
										:label="item.label"
										:icon="item.icon"
										:route="item.route"
										:active="route.path === item.route"
										class="!h-[30px] !rounded-[7px]"
									/>
								</SidebarNavGroup>
							</div>
						</div>

						<!-- Common Pipeline Sections (Quotes, Orders, Production, Install, Reports) -->
						<div v-else-if="pipelineConfig" :key="pipelineConfig.key" class="flex flex-col gap-0.5">
							<SidebarItem
								v-for="item in pipelineConfig.items"
								:key="item.route"
								:label="item.label"
								:icon="item.icon"
								:route="item.route"
								:active="isPipelineItemActive(item.filterKey)"
								class="!h-[30px] !rounded-[7px]"
							/>

							<div v-if="recent.length" class="mt-1.5">
								<SidebarNavGroup :label="pipelineConfig.projectGroupLabel" icon="lucide-folder-kanban" :default-open="false">
									<SidebarItem
										v-for="p in recent"
										:key="p.name"
										:label="p.project_title || p.name"
										icon="lucide-folder"
										:route="`/projects/${p.name}?tab=${pipelineConfig.projectTab}`"
										class="!h-[30px] !rounded-[7px]"
									/>
								</SidebarNavGroup>
							</div>
						</div>

						<!-- Projects -->
						<div v-else key="projects" class="flex flex-col gap-0.5">
							<SidebarItem
								label="All projects"
								icon="lucide-folder-kanban"
								route="/projects"
								:active="route.name === 'Projects'"
								class="!h-[30px] !rounded-[7px]"
							/>

							<div class="mt-1.5">
								<SidebarNavGroup label="Recent projects" icon="lucide-clock" :default-open="true">
									<SidebarItem
										v-for="p in recent"
										:key="p.name"
										:label="p.project_title || p.name"
										icon="lucide-folder"
										:route="`/projects/${p.name}`"
										:active="route.params.project === p.name"
										class="!h-[30px] !rounded-[7px]"
									/>
								</SidebarNavGroup>
							</div>
						</div>
					</Transition>
				</div>
			</div>
		</nav>

		<!-- Main Content -->
		<main class="min-w-0 flex-1 overflow-y-auto" style="scrollbar-gutter: stable">
			<slot />
		</main>

		<!-- Quick Search Modal (⌘K) -->
		<SidebarQuickSearch v-model:open="searchOpen" :items="searchItems" />
	</div>
</template>

<script setup lang="ts">
import {
	Dropdown,
	SidebarItem,
	Tooltip,
	TooltipProvider,
	useList,
} from 'frappe-ui'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { logout } from '@/api'
import { type ModuleKey, PIPELINE_SIDEBAR_CONFIG } from './sidebar/sidebarConfig'
import SidebarNavGroup from './sidebar/SidebarNavGroup.vue'
import SidebarQuickSearch, { type QuickSearchItem } from './sidebar/SidebarQuickSearch.vue'

const props = defineProps<{ user: string; roles: string[] }>()
const route = useRoute()
const router = useRouter()

interface RecentProject {
	name: string
	project_title: string
}

interface RailModule {
	key: ModuleKey
	label: string
	icon: string
	route: string
	active: boolean
}

const studioItems = [
	{ tab: 'series', label: 'Profile Series', icon: 'lucide-layers', route: '/series-studio' },
	{ tab: 'versions', label: 'Series Version', icon: 'lucide-git-branch', route: '/series-studio?tab=versions' },
	{ tab: 'profiles', label: 'Fenestration Profile', icon: 'lucide-ruler', route: '/series-studio?tab=profiles' },
	{ tab: 'glass', label: 'Fenestration Glass', icon: 'lucide-panels-top-left', route: '/series-studio?tab=glass' },
	{ tab: 'hardware', label: 'Fenestration Hardware', icon: 'lucide-wrench', route: '/series-studio?tab=hardware' },
]

const studioCreateItems = [
	{ label: 'New Profile Series', icon: 'lucide-layers', route: '/series-studio/series/new' },
	{ label: 'New Series Version', icon: 'lucide-git-branch', route: '/series-studio/versions/new' },
	{ label: 'New Profile', icon: 'lucide-ruler', route: '/series-studio/profiles/new' },
	{ label: 'New Glass', icon: 'lucide-panels-top-left', route: '/series-studio/glass/new' },
	{ label: 'New Hardware', icon: 'lucide-wrench', route: '/series-studio/hardware/new' },
]

const activeModule = computed<ModuleKey>(() => {
	if (route.path.startsWith('/series-studio')) return 'studio'
	if (route.path.startsWith('/quotes')) return 'quotes'
	if (route.path.startsWith('/orders')) return 'orders'
	if (route.path.startsWith('/production')) return 'production'
	if (route.path.startsWith('/install')) return 'install'
	if (route.path.startsWith('/reports')) return 'reports'
	return 'projects'
})

const pipelineConfig = computed(() => {
	const key = activeModule.value
	if (key === 'projects' || key === 'studio') return null
	return PIPELINE_SIDEBAR_CONFIG[key]
})

const moduleTitle = computed(() => {
	if (activeModule.value === 'studio') return 'Series Studio'
	if (pipelineConfig.value) return pipelineConfig.value.title
	return 'Projects'
})

const activeStudioTab = computed(() => {
	if (route.path.startsWith('/series-studio/profiles')) return 'profiles'
	if (route.path.startsWith('/series-studio/versions')) return 'versions'
	if (route.path.startsWith('/series-studio/glass') || route.path.startsWith('/series-studio/glazing-config')) return 'glass'
	if (route.path.startsWith('/series-studio/hardware')) return 'hardware'
	if (route.path.startsWith('/series-studio/series')) return 'series'
	const t = String(route.query.tab ?? '')
	return ['series', 'versions', 'profiles', 'glass', 'hardware'].includes(t) ? t : 'series'
})
const isEngineer = computed(() => props.roles.some((r) => r === 'System Manager' || r === 'Fenestration Engineer'))
const userInitial = computed(() => (props.user?.trim().charAt(0) || 'U').toUpperCase())

const collapsed = ref(typeof window !== 'undefined' && window.innerWidth < 768)
const searchOpen = ref(false)

const railModules = computed<RailModule[]>(() => {
	const list: RailModule[] = [
		{ key: 'projects', label: 'Projects', icon: 'lucide-folder-kanban', route: '/projects', active: activeModule.value === 'projects' },
		{ key: 'quotes', label: 'Quotes', icon: 'lucide-file-text', route: '/quotes', active: activeModule.value === 'quotes' },
		{ key: 'orders', label: 'Orders', icon: 'lucide-package', route: '/orders', active: activeModule.value === 'orders' },
		{ key: 'production', label: 'Production', icon: 'lucide-factory', route: '/production', active: activeModule.value === 'production' },
		{ key: 'install', label: 'Install', icon: 'lucide-wrench', route: '/install', active: activeModule.value === 'install' },
		{ key: 'reports', label: 'Reports', icon: 'lucide-bar-chart-3', route: '/reports', active: activeModule.value === 'reports' },
	]
	if (isEngineer.value) {
		list.push({ key: 'studio', label: 'Series Studio', icon: 'lucide-layers', route: '/series-studio', active: activeModule.value === 'studio' })
	}
	return list
})

function isPipelineItemActive(filterKey?: string) {
	const current = String(route.query.filter || 'all')
	return current === (filterKey || 'all')
}

function onRailClick(m: RailModule) {
	if (m.active) {
		collapsed.value = !collapsed.value
		return
	}
	collapsed.value = false
	router.push(m.route)
}

const projects = useList<RecentProject>({
	doctype: 'Fenestration Project',
	fields: ['name', 'project_title', 'modified'],
	orderBy: 'modified desc',
	limit: 5,
})
const recent = computed(() => (projects.data ?? []).slice(0, 5))

const moduleMenu = computed(() => {
	const items = railModules.value.map((m) => ({
		label: m.label,
		icon: m.icon,
		onClick: () => router.push(m.route),
	}))
	items.push({
		label: 'Open Desk',
		icon: 'lucide-layout-dashboard',
		onClick: () => (window.location.href = '/app'),
	})
	return items
})

const searchItems = computed<QuickSearchItem[]>(() => {
	const items: QuickSearchItem[] = [
		{ label: 'All projects', group: 'Projects', icon: 'lucide-folder-kanban', route: '/projects' },
		{ label: 'Quotes (All Projects)', group: 'Workspace', icon: 'lucide-file-text', route: '/quotes' },
		{ label: 'Orders (All Projects)', group: 'Workspace', icon: 'lucide-package', route: '/orders' },
		{ label: 'Production (All Projects)', group: 'Workspace', icon: 'lucide-factory', route: '/production' },
		{ label: 'Install (All Projects)', group: 'Workspace', icon: 'lucide-wrench', route: '/install' },
		{ label: 'Reports (All Projects)', group: 'Workspace', icon: 'lucide-bar-chart-3', route: '/reports' },
		...recent.value.map((p) => ({
			label: p.project_title || p.name,
			group: 'Recent project',
			icon: 'lucide-folder',
			route: `/projects/${p.name}`,
		})),
	]
	if (isEngineer.value) {
		items.push(
			...studioItems.map((s) => ({
				label: s.label,
				group: 'Series Studio',
				icon: s.icon,
				route: s.route,
			})),
		)
	}
	return items
})

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

watch(
	() => route.fullPath,
	() => {
		if (typeof window !== 'undefined' && window.innerWidth < 768) {
			collapsed.value = true
		}
	},
)

function handleKeydown(e: KeyboardEvent) {
	if (!(e.metaKey || e.ctrlKey)) return
	const key = e.key.toLowerCase()
	if (key === 'k') {
		e.preventDefault()
		searchOpen.value = !searchOpen.value
	} else if (key === 'b') {
		e.preventDefault()
		collapsed.value = !collapsed.value
	}
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onUnmounted(() => window.removeEventListener('keydown', handleKeydown))
</script>
