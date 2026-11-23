// Use upstream movement and HTMLActuator with the recorded spawn on every move.
const record = JSON.parse(document.querySelector("#record").textContent);
const view = new HTMLActuator();
const slider = document.querySelector("#step");
const button = document.querySelector("#play");
const statusText = document.querySelector("#status");
let current = 0;
let timer = null;
slider.max = record.steps.length;

function reconstruct(index) {
  const state = Object.create(GameManager.prototype);
  state.size = 4;
  state.grid = new Grid(4);
  state.over = false;
  state.won = false;
  state.keepPlaying = true;
  const previous = index > 1 ? record.steps[index - 2] : { board: record.initial, score: 0 };
  state.score = previous.score;
  previous.board.forEach((value, n) => {
    if (value) state.grid.insertTile(new Tile({x: n % 4, y: Math.floor(n / 4)}, value));
  });
  if (index === 0) return state;

  const step = record.steps[index - 1];
  state.addRandomTile = () => {
    const pos = {x: step.spawn.index % 4, y: Math.floor(step.spawn.index / 4)};
    if (!state.grid.cellAvailable(pos)) throw Error("记录的生成位置已被占用");
    state.grid.insertTile(new Tile(pos, step.spawn.value));
  };
  state.actuate = () => {}; // Draw after validating the replayed move.
  state.move(step.action);
  if (state.score !== step.score || !step.board.every((value, n) => {
    const tile = state.grid.cellContent({x: n % 4, y: Math.floor(n / 4)});
    return (tile ? tile.value : 0) === value;
  })) throw Error("原版游戏与记录不一致，步数 " + index);
  return state;
}

function stop() {
  clearInterval(timer);
  timer = null;
  button.textContent = "播放";
}
function show(index) {
  const next = Math.max(0, Math.min(record.steps.length, index));
  try {
    const state = reconstruct(next);
    current = next;
    slider.value = current;
    view.actuate(state.grid, {score: state.score, bestScore: record.raw_score, terminated: false});
    statusText.textContent = "第 " + current + " / " + record.steps.length + " 步" +
      (current ? " · " + ["↑", "→", "↓", "←"][record.steps[current-1].action] : "") +
      " · 本局计分 " + record.score;
  } catch (error) {
    stop();
    statusText.textContent = error.message;
  }
}
button.onclick = () => {
  if (timer !== null) return stop();
  if (current === record.steps.length) show(0);
  button.textContent = "暂停";
  timer = setInterval(() => {
    show(current + 1);
    if (current === record.steps.length) stop();
  }, 180);
};
slider.oninput = () => { stop(); show(Number(slider.value)); };
document.querySelector("#prev").onclick = () => { stop(); show(current-1); };
document.querySelector("#next").onclick = () => { stop(); show(current+1); };
show(0);
