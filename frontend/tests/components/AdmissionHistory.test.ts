import { RouterLinkStub, shallowMount } from '@vue/test-utils'
import { expect, test } from 'vitest'

import AdmissionHistory from '@/components/admission/AdmissionHistory.vue'
import type { Attention } from '@/services/atenciones'

test('el historial reciente enlaza a todas las atenciones del mismo paciente', () => {
  const wrapper = shallowMount(AdmissionHistory, {
    props: {
      entries: [{ id: 9, paciente_id: 100 } as Attention],
      loading: false,
    },
    global: {
      stubs: {
        ElCard: { template: '<div><slot /></div>' },
        ElTable: true,
        ElButton: true,
        RouterLink: RouterLinkStub,
      },
    },
  })
  expect(wrapper.text()).toContain('Últimas 5 atenciones')
  const link = wrapper.getComponent(RouterLinkStub)
  expect(link.text()).toBe('Abrir historial en la ficha')
  expect(link.props('to')).toEqual({
    name: 'paciente-detalle',
    params: { id: 100 },
    query: { tab: 'atenciones' },
  })
  wrapper.unmount()
})

test('permite pedir todas, volver a cinco y refrescar; bloquea los botones durante la carga', async () => {
  const wrapper = shallowMount(AdmissionHistory, {
    props: { entries: [], loading: false },
    global: {
      stubs: {
        ElCard: { template: '<div><slot /></div>' },
        ElTable: true,
        ElButton: {
          props: ['disabled', 'loading'],
          emits: ['click'],
          template:
            '<button :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  })
  const button = (text: string) => wrapper.findAll('button').find((item) => item.text() === text)!
  await button('Traer todas').trigger('click')
  expect(wrapper.emitted('loadAll')).toEqual([[]])

  await wrapper.setProps({ allLoaded: true })
  expect(wrapper.text()).toContain('Historial completo de atenciones')
  await button('Ver últimas 5').trigger('click')
  expect(wrapper.emitted('showRecent')).toEqual([[]])
  await button('Refrescar').trigger('click')
  expect(wrapper.emitted('refresh')).toEqual([[]])

  await wrapper.setProps({ loading: true })
  expect(button('Ver últimas 5').attributes('disabled')).toBeDefined()
  expect(button('Refrescar').attributes('disabled')).toBeDefined()
  wrapper.unmount()
})
