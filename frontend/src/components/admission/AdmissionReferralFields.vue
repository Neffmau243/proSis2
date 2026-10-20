<script setup lang="ts">
const renipress = defineModel<string>('renipress', { required: true })
const name = defineModel<string>('name', { required: true })
const sheet = defineModel<string>('sheet', { required: true })
</script>

<template>
  <div class="referral-fields">
    <el-form-item
      class="admission-context-field"
      label="RENIPRESS"
      prop="referencia_renipress"
    >
      <el-input
        v-model="renipress"
        maxlength="8"
        inputmode="numeric"
        placeholder="8 dígitos"
        aria-label="Código RENIPRESS de origen"
      />
    </el-form-item>
    <el-form-item class="admission-context-field" label="IPRESS" prop="referencia_nombre">
      <el-input v-model="name" maxlength="200" aria-label="Nombre de la IPRESS de origen" />
    </el-form-item>
    <el-form-item class="admission-context-field" label="N.º de hoja" prop="referencia_hoja">
      <el-input v-model="sheet" maxlength="50" aria-label="N.º de hoja de referencia" />
    </el-form-item>
  </div>
</template>

<style scoped>
.referral-fields {
  display: grid;
  gap: 0;
  min-width: 0;
}
.referral-fields :deep(.el-form-item__content) {
  min-width: 0;
  margin-left: 0 !important;
}
</style>
