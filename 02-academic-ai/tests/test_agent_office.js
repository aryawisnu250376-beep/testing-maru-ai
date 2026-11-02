const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const projectRoot = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(projectRoot, 'app/web/index.html'), 'utf8');
const inlineScript = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(inlineScript, 'Agent Office inline script exists');

const drawState = {rects: [], pixelRects: [], texts: [], gradients: 0};
const context2d = {
  font: '8px sans-serif', textAlign: 'left', textBaseline: 'alphabetic',
  beginPath() {}, closePath() {}, moveTo() {}, lineTo() {}, quadraticCurveTo() {},
  bezierCurveTo() {}, arc() {}, ellipse() {}, fill() {}, stroke() {},
  fillRect(x, y, width, height) { drawState.pixelRects.push({x, y, width, height}); },
  clearRect() {}, drawImage() {}, save() {}, restore() {},
  roundRect(x, y, width, height) { drawState.rects.push({x, y, width, height}); },
  createLinearGradient() {
    drawState.gradients += 1;
    return {addColorStop() {}};
  },
  createRadialGradient() {
    drawState.gradients += 1;
    return {addColorStop() {}};
  },
  measureText(text) {
    const size = Number(this.font.match(/([0-9.]+)px/)?.[1] || 8);
    return {width: String(text).length * size * .54};
  },
  fillText(text, x, y) { drawState.texts.push({text, x, y}); }
};
const elements = new Map();
function getElement(id) {
  if (!elements.has(id)) {
    elements.set(id, {
      id, value: '', textContent: '', innerHTML: '', className: '', options: [], files: [], style: {}, dataset: {},
      classList: {contains: () => false, add() {}, remove() {}},
      getContext: () => context2d, addEventListener() {}, appendChild() {}, append() {},
      focus() {}, scrollIntoView() {}, requestSubmit() {}
    });
  }
  return elements.get(id);
}
class MockImage { set src(value) { this._src = value; } }
// Fixed clock: the office sim reads the real time at load (shift + prayer state).
// Pinning it to a work hour keeps navigation/rendering tests deterministic.
const FIXED_EPOCH_MS = Date.parse('2026-01-15T09:00:00+07:00');
class FixedDate extends Date {
  constructor(...args) { super(...(args.length ? args : [FIXED_EPOCH_MS])); }
  static now() { return FIXED_EPOCH_MS; }
}
const sandbox = {
  document: {getElementById: getElement, createElement: () => getElement('created')},
  sessionStorage: {getItem: () => null, setItem() {}, removeItem() {}},
  performance: {now: () => 0},
  requestAnimationFrame: () => 0,
  Image: MockImage,
  Intl, Date: FixedDate, Math, Map, Set, Object, Array, String, Number, Boolean, JSON, Promise,
  URLSearchParams, console,
  fetch: () => Promise.reject(new Error('network disabled in office tests')),
  confirm: () => false,
  FormData: class { append() {} }
};
vm.createContext(sandbox);
vm.runInContext(`${inlineScript}\nglobalThis.__office = {
  officeCrew, OFFICE_AREAS, officeCourses, officeCourseNames, officeDeskPairs,
  routeWorkerTo, moveOfficeWorker, isOfficePointWalkable,
  isOfficeSegmentWalkable, isAllowedOfficeStep, officeAreaAt,
  randomPoint, chooseIdleDestination, drawOfficeCourseLabel, drawOfficeAvatar, drawOfficeBackground,
  getOfficeScheduleState, OFFICE_BREAK_BLOCKS, PRAYER_ROOM_SLOTS, syncOfficeSchedule,
  getJakartaPrayerSchedule, syncOfficePrayer, clearPrayerAssignments,
  setBusy, syncStudyDeskLoading,
  setOfficeZoom, resetOfficeZoom, getOfficeZoom: () => officeZoom, getOfficePan: () => ({x:officePanX, y:officePanY})
};`, sandbox, {timeout: 10000});
const office = sandbox.__office;

assert.equal(office.officeCrew.length, 20, '18 specialist workers plus Owner Arya and Developer Byte');
assert.equal(office.officeCrew.filter(worker => worker.code).length, 14, 'seven subjects have A/B specialists');
for (const worker of office.officeCrew) {
  assert.equal(office.isOfficePointWalkable(worker.homeX, worker.homeY), true, `${worker.name} has a valid workstation position`);
}
const scheduleAt = minute => office.getOfficeScheduleState({minutesOfDay: minute});
assert.equal(scheduleAt(8 * 60).phase, 'work', 'all workers start their shift at 08:00 Jakarta time');
assert.equal(scheduleAt(11 * 60 + 59).phase, 'work', 'the first shift lasts four hours');
assert.equal(scheduleAt(12 * 60).phase, 'break', 'first scheduled break begins at 12:00');
assert.equal(scheduleAt(12 * 60 + 29).phase, 'break', 'first scheduled break lasts 30 minutes');
assert.equal(scheduleAt(12 * 60 + 30).phase, 'work', 'work resumes after the first break');
assert.equal(scheduleAt(16 * 60 + 29).phase, 'work', 'the second work block lasts four hours');
assert.equal(scheduleAt(16 * 60 + 30).phase, 'break', 'second scheduled break begins at 16:30');
assert.equal(scheduleAt(17 * 60).phase, 'off', 'the office shift ends at 17:00');
assert.equal(office.OFFICE_BREAK_BLOCKS.every(block => block.endMinute - block.startMinute === 30), true,
  'each scheduled break lasts 30 minutes');
assert.equal(office.isOfficePointWalkable(160, 160), false, 'owner-room meeting desk is a solid obstacle');
assert.equal(office.isOfficePointWalkable(900, 100), false, 'pantry counter is a solid obstacle');
assert.equal(office.isOfficePointWalkable(800, 470), false, 'lounge seating is a solid obstacle');
for (const areaName of Object.keys(office.OFFICE_AREAS)) {
  for (let sample = 0; sample < 6; sample += 1) {
    const point = office.randomPoint(areaName);
    assert.equal(office.isOfficePointWalkable(point.x, point.y), true, `${areaName} idle destination avoids blocked space`);
  }
}
const scheduleDate = '2026-01-15';
office.syncOfficeSchedule({dateKey:scheduleDate, minutesOfDay:9 * 60});
assert.ok(office.officeCrew.every(worker => worker.onShift && !worker.scheduledBreak
  && worker.destinationArea === worker.homeRoom), 'workers report to their own workstations during the shift');
office.syncOfficeSchedule({dateKey:scheduleDate, minutesOfDay:12 * 60});
assert.ok(office.officeCrew.every(worker => worker.scheduledBreak && worker.destinationArea === 'staff'
  && office.isOfficePointWalkable(worker.breakX, worker.breakY)), 'all workers take a safe, walkable 30-minute break');
assert.ok(office.officeCrew.every(worker => worker.route.length > 0
  || Math.hypot(worker.x - worker.breakX, worker.y - worker.breakY) < 3.1), 'every worker gets a reachable break route');
assert.equal(new Set(office.officeCrew.map(worker => `${worker.breakX},${worker.breakY}`)).size, office.officeCrew.length,
  'break destinations are distinct for all workers');
function simulateScheduleRoute(worker, label) {
  let frame = 0;
  while (worker.route.length && frame < 10000) {
    const previous = {x:worker.x, y:worker.y};
    office.moveOfficeWorker(worker, 1 / 30, frame * 1000 / 30);
    assert.equal(office.isOfficePointWalkable(worker.x, worker.y), true, `${label} stays on walkable floor`);
    if (Math.hypot(worker.x - previous.x, worker.y - previous.y) > .05) {
      assert.equal(office.isOfficeSegmentWalkable(previous, worker.x, worker.y), true, `${label} avoids walls`);
    }
    frame += 1;
  }
  assert.ok(frame < 10000, `${label} route completes`);
}
for (const worker of office.officeCrew) simulateScheduleRoute(worker, `${worker.name} to break`);
assert.ok(office.officeCrew.every(worker => office.officeAreaAt(worker.x, worker.y) === 'staff'),
  'the full team reaches the break area');
office.syncOfficeSchedule({dateKey:scheduleDate, minutesOfDay:12 * 60 + 30});
assert.ok(office.officeCrew.every(worker => worker.onShift && !worker.scheduledBreak
  && worker.destinationArea === worker.homeRoom), 'workers return to their desks after the break');
for (const worker of office.officeCrew) simulateScheduleRoute(worker, `${worker.name} back to workstation`);
assert.ok(office.officeCrew.every(worker => Math.hypot(worker.x - worker.homeX, worker.y - worker.homeY) < 3.1),
  'all workers return to their own desks after the break');
office.syncOfficeSchedule({dateKey:scheduleDate, minutesOfDay:17 * 60});
assert.ok(office.officeCrew.every(worker => !worker.onShift && !worker.scheduledBreak), 'office characters leave their shift at 17:00');

// Full course labels stay within their own workstation pod and never overlap their neighbours.
drawState.rects.length = 0;
drawState.texts.length = 0;
const courseBadges = [];
for (const code of office.officeCourses) {
  const pod = office.OFFICE_AREAS[`pod_${code}`];
  const deskPair = office.officeDeskPairs[code];
  const centerX = (deskPair[0] + deskPair[1]) / 2;
  const availableWidth = 2 * Math.min(centerX - pod.minX, pod.maxX - centerX);
  office.drawOfficeCourseLabel(context2d, code, centerX, 281, availableWidth);
  const rect = drawState.rects.at(-1);
  assert.ok(rect.x >= pod.minX + 3 && rect.x + rect.width <= pod.maxX - 3, `${code} badge fits its pod`);
  assert.equal(drawState.texts.at(-1).text, `${code} · ${office.officeCourseNames[code]}`, `${code} shows its code and full project course name`);
  courseBadges.push(rect);
}
for (let index = 1; index < courseBadges.length; index += 1) {
  assert.ok(courseBadges[index - 1].x + courseBadges[index - 1].width < courseBadges[index].x,
    `course badges ${index - 1} and ${index} do not overlap`);
}

// Door openings are walkable; adjacent solid walls, pod dividers, and the pool rim are not.
for (const roomName of ['boss', 'library', 'manager', 'dev', 'pantry', 'mosque']) {
  const doorX = office.OFFICE_AREAS[roomName].doorX;
  assert.equal(office.isOfficeSegmentWalkable({x: doorX, y: 226}, doorX, 245), true,
    `${roomName} doorway opens to the hall`);
  assert.equal(office.isOfficeSegmentWalkable({x: doorX - 20, y: 226}, doorX - 20, 245), false,
    `${roomName} wall blocks passage away from its door`);
  assert.equal(office.isOfficeSegmentWalkable({x: doorX, y: 252}, doorX, 260), true,
    `${roomName} side of the hall opens to the floor`);
}
for (const code of office.officeCourses) {
  const doorX = office.OFFICE_AREAS[`pod_${code}`].doorX;
  assert.equal(office.isOfficeSegmentWalkable({x: doorX, y: 376}, doorX, 390), true,
    `${code} pod doorway opens to the floor`);
  assert.equal(office.isOfficeSegmentWalkable({x: doorX + 40, y: 376}, doorX + 40, 390), false,
    `${code} pod wall blocks passage away from its door`);
}
assert.equal(office.isOfficeSegmentWalkable({x: 194, y: 354}, 216, 354), false, 'partition between course pods');
assert.equal(office.isOfficePointWalkable(200, 450), false, 'reflecting pool and stone rim');

// Exercise every pair of defined office zones and inspect every movement segment.
const starts = {
  boss: {x: 250, y: 160}, library: {x: 430, y: 205}, manager: {x: 606, y: 205},
  dev: {x: 752, y: 202}, pantry: {x: 860, y: 210}, mosque: {x: 1100, y: 145},
  staff: {x: 650, y: 500}, hall: {x: 1007, y: 245}
};
for (const code of office.officeCourses) {
  const pod = office.OFFICE_AREAS[`pod_${code}`];
  starts[`pod_${code}`] = {x: (pod.minX + pod.maxX) / 2, y: 354};
}
let routeCount = 0;
for (const [sourceArea, start] of Object.entries(starts)) {
  for (const [destinationArea, target] of Object.entries(starts)) {
    const worker = {
      id: `ROUTE_${sourceArea}_${destinationArea}`,
      x: start.x, y: start.y, homeRoom: sourceArea, homeX: start.x, homeY: start.y,
      taskActive: true, prayerDuty: false, praying: false, route: [], waypoint: 0,
      moving: false, phase: 0, pauseUntil: 0, blockedFrames: 0
    };
    office.routeWorkerTo(worker, destinationArea, target.x, target.y);
    let frames = 0;
    while (worker.route.length && frames < 10000) {
      const previous = {x: worker.x, y: worker.y};
      office.moveOfficeWorker(worker, 1 / 30, frames * 1000 / 30);
      assert.equal(office.isOfficePointWalkable(worker.x, worker.y), true,
        `${sourceArea} -> ${destinationArea} stays on walkable floor`);
      if (Math.hypot(worker.x - previous.x, worker.y - previous.y) > .05) {
        assert.equal(office.isOfficeSegmentWalkable(previous, worker.x, worker.y), true,
          `${sourceArea} -> ${destinationArea} never clips through a wall`);
      }
      frames += 1;
    }
    assert.ok(frames < 10000, `${sourceArea} -> ${destinationArea} route terminates`);
    assert.ok(Math.hypot(worker.x - target.x, worker.y - target.y) < 3.1,
      `${sourceArea} -> ${destinationArea} reaches its target`);
    routeCount += 1;
  }
}
assert.equal(routeCount, 225, 'all zone-to-zone routes were simulated');

// Only one idle worker may reserve or occupy the narrow Pantry at a time.
const [pantryGuest, nextGuest] = office.officeCrew;
pantryGuest.destinationArea = 'pantry';
const originalRandom = Math.random;
try {
  Math.random = () => .5;
  office.chooseIdleDestination(nextGuest);
} finally {
  Math.random = originalRandom;
}
assert.notEqual(nextGuest.destinationArea, 'pantry', 'the Pantry entry queue is kept clear');

// Render one frame and all course labels into a Canvas-compatible mock context.
const labelsBefore = drawState.texts.length;
office.drawOfficeBackground(context2d, 0, {timeText: '12:00', minutesOfDay: 720, dateKey: '2026-10-08', year: 2026, month: 10, day: 8, hour: 12});
assert.ok(drawState.texts.length > labelsBefore, 'room and course labels remain visible');
drawState.pixelRects.length = 0;
office.drawOfficeAvatar(context2d, office.officeCrew[0], 500);
assert.ok(drawState.pixelRects.length >= 12, 'avatars render with compact block-style pixel shapes');
assert.ok(drawState.texts.some(item => item.text.includes('Pengantar Ilmu Komunikasi')), 'full subject names are drawn');
office.resetOfficeZoom();
assert.equal(office.getOfficeZoom(), 1, 'office zoom reset returns to 100 percent');
office.setOfficeZoom(1.5, 900, 400);
assert.equal(office.getOfficeZoom(), 1.5, 'office map supports interactive zoom');
const officePan = office.getOfficePan();
assert.ok(Math.abs(officePan.x) <= 600 * .5 && Math.abs(officePan.y) <= 337.5 * .5,
  'zoom pan remains clamped to the office map');
office.setOfficeZoom(99);
assert.equal(office.getOfficeZoom(), 2.75, 'office zoom has a safe upper bound');
office.setOfficeZoom(.2);
assert.equal(office.getOfficeZoom(), 1, 'office zoom cannot leave empty space outside the map');
const prayerDate = {dateKey:'2026-01-15', year:2026, month:1, day:15, minutesOfDay:0};
const nextPrayer = office.getJakartaPrayerSchedule(prayerDate)[0];
const prayerClock = {...prayerDate, minutesOfDay:nextPrayer.minute + 1};
const taskWorker = office.officeCrew[0];
taskWorker.taskActive = true;
const taskRouteBeforePrayer = taskWorker.route.slice();
office.syncOfficePrayer(prayerClock);
assert.equal(taskWorker.prayerDuty, false, 'a worker handling an active task is not diverted to prayer');
assert.deepEqual(taskWorker.route, taskRouteBeforePrayer, 'an active-task route remains unchanged at prayer time');
assert.equal(office.officeCrew.filter(worker => worker.prayerDuty && !worker.taskActive).length, 19,
  'all idle characters receive a prayer-time break');
assert.equal(office.officeCrew.filter(worker => worker.prayerDuty && worker.prayerSlot >= 0).length, 4,
  'only the four available Mushola places receive visitors at once');
const deskLoader = getElement('studyDeskLoader');
office.setBusy(getElement('summaryBtn'), true, 'Merangkum...');
assert.equal(deskLoader.hidden, false, 'AI Study Desk loader appears while a summary is running');
assert.equal(getElement('studyDeskLoadingTitle').textContent, 'AI sedang merangkum materi', 'summary loader has the correct status');
office.setBusy(getElement('summaryBtn'), false, 'Ringkas materi');
assert.equal(deskLoader.hidden, true, 'AI Study Desk loader hides after the summary finishes');
office.setBusy(getElement('quizBtn'), true, 'Membuat kuis...');
assert.equal(deskLoader.hidden, false, 'AI Study Desk loader appears while a quiz is running');
assert.equal(getElement('studyDeskLoadingTitle').textContent, 'AI sedang menyusun kuis', 'quiz loader has the correct status');
office.setBusy(getElement('quizBtn'), false, 'Buat kuis');
office.setBusy(getElement('sendBtn'), true, 'Mengirim...');
assert.equal(deskLoader.hidden, false, 'AI Study Desk loader appears while a chat answer is running');
assert.equal(getElement('studyDeskLoadingTitle').textContent, 'Tim AI sedang menjawab', 'chat loader has the correct status');
office.setBusy(getElement('sendBtn'), false, 'Kirim pertanyaan');
assert.equal(deskLoader.hidden, true, 'AI Study Desk loader hides when no AI action remains active');
office.setBusy(getElement('youtubeBtn'), true, 'Mengambil caption...');
assert.equal(deskLoader.hidden, false, 'AI Study Desk loader appears while YouTube captions are summarized');
assert.equal(getElement('studyDeskLoadingTitle').textContent, 'AI sedang merangkum video', 'YouTube loader explains its status');
office.setBusy(getElement('youtubeBtn'), false, 'Ringkas');
office.setBusy(getElement('transcribeBtn'), true, 'Transkrip...');
assert.equal(deskLoader.hidden, false, 'AI Study Desk loader appears while audio is transcribed');
assert.equal(getElement('studyDeskLoadingTitle').textContent, 'Menyalin voice note', 'voice-note loader explains its STT status');
office.setBusy(getElement('transcribeBtn'), false, 'Transkripkan');
assert.equal(deskLoader.hidden, true, 'AI Study Desk loader hides after audio transcription');
assert.ok(html.includes('id="username"') && html.includes('id="password"') && html.includes('id="loginBtn"'),
  'Study Desk includes username/password login instead of manual token entry');
assert.ok(html.includes('id="youtubeUrl"') && html.includes('id="recordBtn"') && html.includes('id="audioFile"'),
  'Study Desk includes YouTube, microphone recording, and audio-upload controls');

console.log(`Agent Office checks passed: ${routeCount} routes, shift/break schedule, zoom, prayer-task protection, AI Study Desk chat/summary/quiz/media loaders, username/password login, YouTube and voice controls, doorway/wall/pool collisions, 7 course labels, and avatar rendering.`);
