<template>
  <FrappeUIProvider>
    <RouterView v-if="$route.meta.fullscreen" />
    <AppShell v-else-if="session" :user="session.user" :roles="session.roles">
      <RouterView />
    </AppShell>
  </FrappeUIProvider>
</template>

<script setup lang="ts">
import { FrappeUIProvider } from 'frappe-ui'
import { onMounted, ref } from 'vue'
import { RouterView } from 'vue-router'
import { getSession, type Session } from '@/api'
import AppShell from '@/components/AppShell.vue'

const session = ref<Session | null>(null)

onMounted(async () => {
  const s = await getSession()
  if (s.user === 'Guest') {
    window.location.href = '/login?redirect-to=/fenestration'
    return
  }
  session.value = s
})
</script>
