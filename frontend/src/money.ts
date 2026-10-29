const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' })

export function formatMoney(amount: number | null | undefined): string {
	return inr.format(amount ?? 0)
}
