<template>
  <div class="max-w-xl mx-auto p-4">
    <div class="flex justify-between mb-3">
      <h1 class="text-xl font-semibold">My parcels</h1>
      <router-link to="/book"><Button variant="solid">New parcel</Button></router-link>
    </div>
    <div v-for="p in parcels.data" :key="p.name" class="border rounded p-3 mb-2">
      <div class="font-medium">{{ p.name }} to {{ p.recipient_name }}, {{ p.destination_city }}</div>
      <div class="text-sm text-gray-600">{{ p.status }}</div>
      <router-link class="text-blue-600 mr-3" :to="'/track/' + p.name">Track</router-link>
      <router-link v-if="p.payment_status === 'Paid'" class="text-blue-600" :to="'/label/' + p.name">Label</router-link>
    </div>
  </div>
</template>

<script setup>
import { Button, createResource } from 'frappe-ui'

const parcels = createResource({ url: 'courier.api.my_parcels', auto: true })
</script>
