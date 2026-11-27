import type { PipelineSection } from '@/api'
import { formatMoney } from '@/money'

export interface StatCardItem {
	label: string
	value: string | number
	sublabel: string
	icon: string
}

export interface SectionMeta {
	title: string
	subtitle: string
	searchPlaceholder: string
	emptyText: string
}

export const SECTION_META: Record<PipelineSection, SectionMeta> = {
	quotes: {
		title: 'Quotes',
		subtitle: 'Overall commercial quotations across all fenestration projects.',
		searchPlaceholder: 'Search quotes, projects, or customers',
		emptyText: 'No quotations found across projects.',
	},
	orders: {
		title: 'Orders',
		subtitle: 'Overall sales orders and delivery fulfillment across all projects.',
		searchPlaceholder: 'Search orders, projects, or customers',
		emptyText: 'No sales orders found across projects.',
	},
	production: {
		title: 'Production',
		subtitle: 'Overall work orders, material requests, and purchase orders across all projects.',
		searchPlaceholder: 'Search work orders, MRs, POs, or projects',
		emptyText: 'No production or procurement documents found across projects.',
	},
	install: {
		title: 'Install',
		subtitle: 'Overall site dispatches, delivery notes, and installation readiness across projects.',
		searchPlaceholder: 'Search deliveries, sites, or projects',
		emptyText: 'No delivery notes or pending dispatches found.',
	},
	reports: {
		title: 'Reports',
		subtitle: 'Overall project metrics and printable engineering & commercial reports.',
		searchPlaceholder: 'Search projects or customers',
		emptyText: 'No project report data available yet.',
	},
}

export function buildStatCards(section: PipelineSection, stats: Record<string, number>): StatCardItem[] {
	switch (section) {
		case 'quotes':
			return [
				{ label: 'Total Quotes', value: stats.total ?? 0, sublabel: 'Across all projects', icon: 'lucide-file-text' },
				{ label: 'Draft', value: stats.draft ?? 0, sublabel: 'Awaiting submission', icon: 'lucide-file-edit' },
				{ label: 'Submitted / Open', value: stats.submitted ?? 0, sublabel: `${stats.ordered ?? 0} converted to order`, icon: 'lucide-send' },
				{ label: 'Quoted Value', value: formatMoney(stats.total_value ?? 0), sublabel: 'Active quotation total', icon: 'lucide-indian-rupee' },
			]
		case 'orders':
			return [
				{ label: 'Total Orders', value: stats.total ?? 0, sublabel: `${stats.draft ?? 0} draft`, icon: 'lucide-package' },
				{ label: 'To Deliver', value: stats.to_deliver ?? 0, sublabel: 'Awaiting dispatch', icon: 'lucide-truck' },
				{ label: 'Completed', value: stats.completed ?? 0, sublabel: 'Delivered & billed', icon: 'lucide-check-circle' },
				{ label: 'Order Value', value: formatMoney(stats.total_value ?? 0), sublabel: 'Active sales order total', icon: 'lucide-indian-rupee' },
			]
		case 'production':
			return [
				{ label: 'Work Orders', value: stats.work_orders ?? 0, sublabel: `${stats.in_progress ?? 0} active`, icon: 'lucide-factory' },
				{ label: 'Material Requests', value: stats.material_requests ?? 0, sublabel: 'BOM procurement requests', icon: 'lucide-clipboard-list' },
				{ label: 'Purchase Orders', value: stats.purchase_orders ?? 0, sublabel: 'Supplier orders', icon: 'lucide-shopping-cart' },
				{ label: 'Completed Units', value: stats.completed_units ?? 0, sublabel: 'Produced windows', icon: 'lucide-check-square' },
			]
		case 'install':
			return [
				{ label: 'Delivery Notes', value: stats.total_deliveries ?? 0, sublabel: 'Dispatched shipments', icon: 'lucide-truck' },
				{ label: 'Pending Dispatch', value: stats.pending_dispatch ?? 0, sublabel: 'Orders awaiting delivery', icon: 'lucide-clock' },
				{ label: 'Dispatched Qty', value: stats.dispatched_qty ?? 0, sublabel: 'Windows shipped to site', icon: 'lucide-package-check' },
				{ label: 'Installed Deliveries', value: stats.installed_count ?? 0, sublabel: '100% installed', icon: 'lucide-wrench' },
			]
		case 'reports':
			return [
				{ label: 'Projects Covered', value: stats.total_projects ?? 0, sublabel: 'Active portfolio', icon: 'lucide-folder-kanban' },
				{ label: 'Total Windows', value: stats.total_windows ?? 0, sublabel: 'Combined unit qty', icon: 'lucide-layout-grid' },
				{ label: 'Total Area', value: `${stats.total_area_sqft ?? 0} sq.ft`, sublabel: `${stats.total_weight_kg ?? 0} kg total weight`, icon: 'lucide-ruler' },
				{ label: 'Portfolio Value', value: formatMoney(stats.total_value ?? 0), sublabel: 'Combined design value', icon: 'lucide-indian-rupee' },
			]
	}
}

