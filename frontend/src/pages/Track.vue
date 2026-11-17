<template>
  <div class="max-w-xl mx-auto p-4">
    <h1 class="text-xl font-semibold">{{ name }}</h1>
    <p class="mb-3">Status: {{ info.data?.status }}</p>
    <p v-if="info.data?.status === 'Unpaid'" class="text-sm text-gray-600">Waiting for payment confirmation...</p>

    <ul class="border-l-2 pl-4">
      <li v-for="e in info.data?.events" :key="e.creation" class="mb-2">
        <div>{{ e.status }}<span v-if="e.hub"> ({{ e.hub }})</span></div>
        <div class="text-sm text-gray-500">{{ e.creation }}</div>
      </li>
    </ul>

    <Button v-if="info.data?.status === 'Delivered'" class="mt-4" @click="startReturn">Return this parcel</Button>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { Button, call, createResource } from 'frappe-ui'

const props = defineProps({ name: String })
const info = createResource({ url: 'courier.api.track_parcel', params: { name: props.name }, auto: true })

// refresh every 10 seconds so the timeline stays live
let timer
onMounted(() => (timer = setInterval(() => info.reload(), 10000)))
onUnmounted(() => clearInterval(timer))

async function startReturn() {
  await call('courier.api.raise_return', { name: props.name })
  info.reload()
}
</script>
