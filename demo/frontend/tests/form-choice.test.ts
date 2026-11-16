import assert from 'node:assert/strict'
import test from 'node:test'
import { choiceSatisfied, circleMarkBox, toggledChoices, type ChoiceField } from '../src/lib/form-choice.ts'

const word = (group: string): ChoiceField => ({ field_type: 'radio', group, choice_mark: 'circle' })
const fields: [string, ChoiceField][] = [
  ['yes', word('g1')], ['no', word('g1')], ['other_yes', word('g2')], ['box', { field_type: 'check', group: 'g3' }],
]

test('choosing one word of a pair clears the other word of the same group only', () => {
  const first = toggledChoices({}, fields, 'yes', true)
  assert.deepEqual(first, { yes: true, no: false })
  const switched = toggledChoices({ ...first, other_yes: true }, fields, 'no', true)
  assert.equal(switched.yes, false)
  assert.equal(switched.no, true)
  assert.equal(switched.other_yes, true)
})

test('plain checks and unchecking never touch other fields', () => {
  assert.deepEqual(toggledChoices({ yes: true }, fields, 'box', true), { yes: true, box: true })
  assert.deepEqual(toggledChoices({ yes: true, no: false }, fields, 'yes', false), { yes: false, no: false })
})

test('a required choice group is satisfied by either word, a plain check only by itself', () => {
  assert.equal(choiceSatisfied({}, fields, 'yes'), false)
  assert.equal(choiceSatisfied({ no: true }, fields, 'yes'), true)
  assert.equal(choiceSatisfied({ other_yes: true }, fields, 'yes'), false)
  assert.equal(choiceSatisfied({ yes: true }, fields, 'box'), false)
})

test('the circle surrounds the word box with the renderer padding', () => {
  assert.deepEqual(circleMarkBox([0, 0, 30, 10]), [-3.5, -3, 33.5, 13])
  assert.deepEqual(circleMarkBox([0, 0, 30, 4]), [-2, -1.5, 32, 5.5])
})
