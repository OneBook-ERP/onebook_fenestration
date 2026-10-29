<template>
  <FrappeUIProvider>
    <div v-if="sessionError" class="mx-auto flex max-w-md flex-col gap-3 p-6">
      <Alert theme="red" title="Could not load your session. Reload the page." />
      <Button label="Reload" class="min-h-9 self-start" @click="reload" />
    </div>
    <RouterView v-else-if="$route.meta.fullscreen" />
    <AppShell v-else-if="session" :user="session.user" :roles="session.roles">
      <RouterView :key="$route.fullPath" />
    </AppShell>
  </FrappeUIProvider>
</template>

<script setup lang="ts">
import { Alert, Button, FrappeUIProvider } from 'frappe-ui'
import { onMounted, ref } from 'vue'
import { RouterView } from 'vue-router'
import { getSession, type Session } from '@/api'
import AppShell from '@/components/AppShell.vue'

const session = ref<Session | null>(null)
const sessionError = ref(false)
const reload = () => window.location.reload()

onMounted(async () => {
  let s: Session
  try {
    s = await getSession()
  } catch {
    sessionError.value = true
    return
  }
  if (s.user === 'Guest') {
    const { pathname, search } = window.location
    window.location.href = '/login?redirect-to=' + encodeURIComponent(pathname + search)
    return
  }
  session.value = s
})
</script>
