<script setup lang="ts">
import { computed } from 'vue'
import { gestationalAgeFromDueDate } from '@/utils/pregnancy'

const props = defineProps<{ attendedAt: string; dueOn: string | null }>()
const assessedWeeks = defineModel<number | null>({ required: true })
const calculated = computed(() => gestationalAgeFromDueDate(props.attendedAt, props.dueOn))
</script>

<template>
  <div>
    <el-form-item class="measurement-field" label="Edad gestacional (semanas)">
      <el-input-number
        :model-value="assessedWeeks ?? calculated?.weeks ?? null"
        :min="0" :max="45" :precision="0" :controls="false"
        aria-label="Edad gestacional en semanas"
        style="width: 100%"
        @update:model-value="assessedWeeks = $event ?? null"
      />
    </el-form-item>
    <p v-if="assessedWeeks != null || calculated" class="gestational-age-help" role="status">
      <template v-if="assessedWeeks != null">
        Se imprimirá la edad valorada por el profesional.
        <el-button v-if="calculated" link type="primary" @click="assessedWeeks = null">
          Usar cálculo por FPP
        </el-button>
      </template>
      <template v-else-if="calculated">
        Según FPP: {{ calculated.weeks }} semanas y {{ calculated.days }} días.
        Verifique antes de guardar.
      </template>
    </p>
  </div>
</template>

<style scoped>
.gestational-age-help {
  margin: 0 0 8px;
  color: var(--el-text-color-regular);
  font-size: 14px;
  line-height: 1.5;
}
</style>
