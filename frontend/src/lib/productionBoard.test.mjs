import assert from 'node:assert/strict'
import {
  mergeProductionBoard,
  pinProductionRun,
  unpinProductionRun,
} from './productionBoard.js'

function run(id, title = `R${id}`) {
  return { id, title, status: 'active', steps: [] }
}

// Fresh create must survive a later empty server board (the ui-v1.16 residual race).
{
  const created = run(42, 'Geburtstagsring')
  const pins = pinProductionRun({}, created)
  const afterCreate = mergeProductionBoard([created], {
    pins,
    ensureRun: created,
    previousBoard: [],
  })
  assert.equal(afterCreate.length, 1)
  assert.equal(afterCreate[0].id, 42)

  const wiped = mergeProductionBoard([], {
    pins,
    ensureRun: null,
    previousBoard: afterCreate,
  })
  assert.equal(wiped.length, 1, 'empty reload must not drop pinned/previous runs')
  assert.equal(wiped[0].id, 42)
}

// Explicit allowEmptyWipe (after complete) may clear.
{
  const prev = [run(7)]
  const empty = mergeProductionBoard([], {
    pins: {},
    previousBoard: prev,
    allowEmptyWipe: true,
  })
  assert.equal(empty.length, 0)
}

// Server wins when it returns the run; pins fill gaps only.
{
  const server = [run(1, 'A'), run(2, 'B')]
  const pins = pinProductionRun({}, run(3, 'C'))
  const merged = mergeProductionBoard(server, { pins, previousBoard: server })
  assert.deepEqual(
    merged.map((r) => r.id),
    [3, 2, 1],
  )
}

// unpin removes completed local pin
{
  let pins = pinProductionRun({}, run(9))
  pins = unpinProductionRun(pins, 9)
  assert.equal(Object.keys(pins).length, 0)
}

console.log('productionBoard.test.mjs: ok')
