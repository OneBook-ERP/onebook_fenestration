export type ModuleKey = 'projects' | 'quotes' | 'orders' | 'production' | 'install' | 'reports' | 'studio'

export interface SidebarSubItem {
	label: string
	icon: string
	route: string
	filterKey?: string
}

export interface ModuleSectionConfig {
	key: Exclude<ModuleKey, 'projects' | 'studio'>
	title: string
	baseRoute: string
	projectTab: string
	projectGroupLabel: string
	items: SidebarSubItem[]
}

export const PIPELINE_SIDEBAR_CONFIG: Record<
	Exclude<ModuleKey, 'projects' | 'studio'>,
	ModuleSectionConfig
> = {
	quotes: {
		key: 'quotes',
		title: 'Quotes',
		baseRoute: '/quotes',
		projectTab: 'quote',
		projectGroupLabel: 'By project',
		items: [
			{ label: 'All quotes', icon: 'lucide-file-text', route: '/quotes', filterKey: 'all' },
			{ label: 'Draft quotes', icon: 'lucide-file-edit', route: '/quotes?filter=draft', filterKey: 'draft' },
			{ label: 'Submitted', icon: 'lucide-send', route: '/quotes?filter=open', filterKey: 'open' },
			{ label: 'Ordered', icon: 'lucide-check-circle', route: '/quotes?filter=ordered', filterKey: 'ordered' },
		],
	},
	orders: {
		key: 'orders',
		title: 'Orders',
		baseRoute: '/orders',
		projectTab: 'order',
		projectGroupLabel: 'By project',
		items: [
			{ label: 'All orders', icon: 'lucide-package', route: '/orders', filterKey: 'all' },
			{ label: 'To deliver', icon: 'lucide-truck', route: '/orders?filter=to_deliver', filterKey: 'to_deliver' },
			{ label: 'Completed', icon: 'lucide-check-circle', route: '/orders?filter=completed', filterKey: 'completed' },
		],
	},
	production: {
		key: 'production',
		title: 'Production',
		baseRoute: '/production',
		projectTab: 'production',
		projectGroupLabel: 'Project BOM',
		items: [
			{ label: 'All production', icon: 'lucide-factory', route: '/production', filterKey: 'all' },
			{ label: 'Work Orders', icon: 'lucide-cog', route: '/production?filter=wo', filterKey: 'wo' },
			{ label: 'Material Requests', icon: 'lucide-clipboard-list', route: '/production?filter=mr', filterKey: 'mr' },
			{ label: 'Purchase Orders', icon: 'lucide-shopping-cart', route: '/production?filter=po', filterKey: 'po' },
		],
	},
	install: {
		key: 'install',
		title: 'Install',
		baseRoute: '/install',
		projectTab: 'install',
		projectGroupLabel: 'By project',
		items: [
			{ label: 'All dispatches', icon: 'lucide-wrench', route: '/install', filterKey: 'all' },
			{ label: 'Pending dispatch', icon: 'lucide-clock', route: '/install?filter=pending', filterKey: 'pending' },
			{ label: 'Deliveries', icon: 'lucide-truck', route: '/install?filter=delivery', filterKey: 'delivery' },
		],
	},
	reports: {
		key: 'reports',
		title: 'Reports',
		baseRoute: '/reports',
		projectTab: 'reports',
		projectGroupLabel: 'Project reports',
		items: [
			{ label: 'All project reports', icon: 'lucide-bar-chart-3', route: '/reports', filterKey: 'all' },
			{ label: 'Quoted / Ordered', icon: 'lucide-file-check', route: '/reports?filter=quoted', filterKey: 'quoted' },
		],
	},
}

