import type { DealStage, PipelineColumn } from '../api/types'

/**
 * Pure helper used for the optimistic update when a card is dropped on another column.
 * Returns a new board with the deal moved and the column counts / totals recomputed.
 */
export function moveDeal(board: PipelineColumn[], dealId: number, to: DealStage): PipelineColumn[] {
  const deal = board.flatMap((c) => c.deals).find((d) => d.id === dealId)
  if (!deal || deal.stage === to) return board

  const moved = { ...deal, stage: to, stage_label: board.find((c) => c.stage === to)?.label ?? deal.stage_label }

  return board.map((column) => {
    let deals = column.deals.filter((d) => d.id !== dealId)
    if (column.stage === to) deals = [moved, ...deals]
    return {
      ...column,
      deals,
      count: deals.length,
      total_value: deals.reduce((sum, d) => sum + d.value, 0),
    }
  })
}
