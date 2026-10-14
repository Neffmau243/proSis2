import type { InjectionKey, Ref } from 'vue'

/** Destination for page controls that keep their original component/form context. */
export const topbarActionsKey: InjectionKey<Readonly<Ref<HTMLElement | null>>> =
  Symbol('topbarActions')
