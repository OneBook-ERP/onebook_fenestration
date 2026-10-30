import { useList } from 'frappe-ui'
import { computed, type Ref } from 'vue'

interface ProfileRow {
	name: string
	profile_name: string
}

/** profile_code -> profile_name, loaded once from Fenestration Profile. */
export function useProfileNames(): Ref<Record<string, string>> {
	const list = useList<ProfileRow>({
		doctype: 'Fenestration Profile',
		fields: ['name', 'profile_name'],
		limit: 500,
	})
	return computed(() => Object.fromEntries((list.data ?? []).map((p) => [p.name, p.profile_name])))
}
