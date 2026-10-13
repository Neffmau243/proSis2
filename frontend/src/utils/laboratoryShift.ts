/** Horarios de Lima acordados para este centro; límites finales excluyentes. */
export const laboratoryShifts = [
  { name: 'Mañana', start: '07:00:00', end: '13:00:00' },
  { name: 'Tarde', start: '13:00:00', end: '19:00:00' },
] as const

export function laboratoryShift(dateTime: string) {
  const [day, rawTime = ''] = dateTime.split('T')
  const time = rawTime.length === 5 ? `${rawTime}:00` : rawTime
  const shift = laboratoryShifts.find((item) => time >= item.start && time < item.end)
  return shift && day
    ? {
        name: shift.name,
        start: `${day}T${shift.start}`,
        end: `${day}T${shift.end}`,
      }
    : null
}
