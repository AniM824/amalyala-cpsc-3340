const BORDER = 25; 
const MIN_HOUSE = 200;
const MIN_FLOOR_H = 100;
const MIN_ROOM_W = 100;
const MAX_FLOORS = 30;
const MAX_ROOMS = 30;
const OBJECT_SPACING = 200;

function randomColor() {
    return [random(255), random(255), random(255)];
}

const LIT_HOLD_MIN = 2500;
const LIT_HOLD_MAX = 8000;
const FADE_OUT_MIN = 900;
const FADE_OUT_MAX = 2200;
const DARK_HOLD_MIN = 2000;
const DARK_HOLD_MAX = 6000;
const FADE_IN_MIN = 900;
const FADE_IN_MAX = 2200;

function rollPhases(room) {
    room.litHold = random(LIT_HOLD_MIN, LIT_HOLD_MAX);
    room.fadeOut = random(FADE_OUT_MIN, FADE_OUT_MAX);
    room.darkHold = random(DARK_HOLD_MIN, DARK_HOLD_MAX);
    room.fadeIn = random(FADE_IN_MIN, FADE_IN_MAX);
    room.cycleLen = room.litHold + room.fadeOut + room.darkHold + room.fadeIn;
}

function initRoomLife(room) {
    rollPhases(room);
    room.cycleStart = millis() - random(room.cycleLen);
    room.reshuffled = false;
    room.person = makePersonState(room);
    room.furniture = makeFurnitureState(room);
    room.glassStreaks = makeGlassStreaks(room);
}

function reshuffleRoom(room) {
    room.col = randomColor();
    room.person = makePersonState(room);
    room.furniture = makeFurnitureState(room);
    room.glassStreaks = makeGlassStreaks(room);
}

function makeGlassStreaks(room) {
    const gap = random(0.28, 0.42);
    const base = random(0.15, 0.35);
    return [
        { offset: base, width: random(0.16, 0.24) },
        { offset: base + gap, width: random(0.1, 0.16) },
    ];
}

function roomVisibility(room) {
    const elapsed = (millis() - room.cycleStart) % room.cycleLen;

    const litEnd = room.litHold;
    const fadeOutEnd = litEnd + room.fadeOut;
    const darkEnd = fadeOutEnd + room.darkHold;

    if (elapsed < litEnd) {
        room.reshuffled = false;
        return 1;
    } else if (elapsed < fadeOutEnd) {
        return 1 - (elapsed - litEnd) / room.fadeOut;
    } else if (elapsed < darkEnd) {
        if (!room.reshuffled) {
            reshuffleRoom(room);
            if (random() < 0.5) {
                rollPhases(room);
                room.cycleStart = millis() - (room.litHold + room.fadeOut);
            }
            room.reshuffled = true;
        }
        return 0;
    } else {
        return (elapsed - darkEnd) / room.fadeIn;
    }
}

let house;
let roof;
let rooms = [];

function setup() {
    createCanvas(windowWidth, windowHeight);
    noCursor();
    generateHouse();
}

function draw() {
    background(185, 215, 235);
    drawChimney();
    drawRoof();
    drawRooms();
    drawAtticWindow();
}

function windowResized() {
    resizeCanvas(windowWidth, windowHeight);
    generateHouse();
}

function generateHouse() {
    rooms = [];
    extras = {};

    const availW = width - 2 * BORDER;
    const availH = height - 2 * BORDER;

    if (availW < MIN_HOUSE || availH < MIN_HOUSE) {
        const size = max(min(width, height) * 0.8, 1);
        const x = (width - size) / 2;
        const y = (height - size) / 2;
        const roofH = size * 0.4;
        roof = {x1: x, y1: y + roofH, x2: x + size, y2: y + roofH, x3: x + size / 2, y3: y, h: roofH};
        roof.col = randomColor();
        roof.chimneyCol = randomColor();
        roof.windowCol = randomColor();
        house = {x: x, y: y + roofH, w: size, h: size - roofH};
        const soloRoom = { ...house, type: "living", col: randomColor() };
        initRoomLife(soloRoom);
        rooms.push(soloRoom);
        return;
    }

    const roofH = constrain(availW * 0.3, MIN_FLOOR_H, availH / 3);
    house = { x: BORDER, y: BORDER + roofH, w: availW, h: availH - roofH };
    roof = { x1: house.x, y1: house.y, x2: house.x + house.w, y2: house.y, x3: house.x + house.w / 2, y3: BORDER, h: roofH };
    roof.col = randomColor();
    roof.chimneyCol = randomColor();
    roof.windowCol = randomColor();

    let maxFloors = MAX_FLOORS;
    let maxRooms = MAX_ROOMS;

    const floorHeights = splitLength(house.h, MIN_FLOOR_H, maxFloors);
    let y = house.y;
    for (let f = 0; f < floorHeights.length; f++) {
        const h = floorHeights[f];
        const widths = splitLength(house.w, MIN_ROOM_W, maxRooms);
        let x = house.x;
        for (const w of widths) {
            const room = { x: x, y: y, w: w, h: h };
            room.type = assignRoomType(room, f, floorHeights.length);
            room.col = randomColor();
            initRoomLife(room);
            rooms.push(room);
            x += w;
        }
        y += h;
    }
}

function splitLength(total, minSize, maxCount) {
    const lo = max(minSize, total / maxCount);
    const hi = max(total / 3, lo);
    const sizes = [];
    let remaining = total;

    while (remaining > 0) {
        if (remaining < 2 * lo) {
            sizes.push(remaining);
            break;
        }
        const s = random(lo, min(hi, remaining - lo));
        sizes.push(s);
        remaining -= s;
    }
    return sizes;
}

function assignRoomType(room, floorIndex, floorCount) {
    if (room.w < 150){
        return "closet";
    }
    return random(["bedroom", "bedroom", "bath"]);
}

function drawRoof() {
    fill(roof.col);
    stroke(60);
    strokeWeight(3);
    triangle(roof.x1, roof.y1, roof.x2, roof.y2, roof.x3, roof.y3);
}

function drawRooms() {
    for (const room of rooms) {
        drawRoom(room);
    }
}


const GLASS_COL = [150, 182, 205];
function drawRoom(room) {
    const vis = roomVisibility(room);

    const shadowOffset = 5;
    noStroke();
    fill(0, 0, 0, 35);
    rect(room.x + shadowOffset, room.y + shadowOffset, room.w, room.h);

    const litCol = room.col;
    const glassAmount = 1 - vis;
    const r = lerp(litCol[0], GLASS_COL[0], glassAmount);
    const g = lerp(litCol[1], GLASS_COL[1], glassAmount);
    const b = lerp(litCol[2], GLASS_COL[2], glassAmount);
    fill(r, g, b);
    stroke(60, lerp(255, 200, glassAmount));
    strokeWeight(3);
    rect(room.x, room.y, room.w, room.h);

    if (glassAmount > 0.02) {
        drawGlassStreaks(room, glassAmount);
        drawGlassEdge(room, glassAmount);
    }

    if (vis > 0.02) {
        drawRoomShading(room, vis);
        drawFurniture(room, vis);
        drawPerson(room, 255 * vis);
    }
}

function drawGlassEdge(room, glassAmount) {
    noFill();
    strokeCap(SQUARE);
    stroke(255, 255, 255, 90 * glassAmount);
    strokeWeight(2);
    line(room.x + 2, room.y + room.h - 4, room.x + 2, room.y + 2);
    line(room.x + 2, room.y + 2, room.x + room.w - 4, room.y + 2);
}

//ai assist but mostly me still
function drawGlassStreaks(room, glassAmount) {
    push();
    drawingContext.beginPath();
    drawingContext.rect(room.x, room.y, room.w, room.h);
    drawingContext.clip();

    noStroke();
    rectMode(CENTER);

    const diag = dist(0, 0, min(room.w, room.h), min(room.w, room.h));
    const angle = atan2(room.h, room.h);
    const dx = cos(angle);
    const dy = sin(angle);
    const bandLen = diag * 1.6;

    const steps = 14;
    for (const band of room.glassStreaks) {
        const midDist = band.offset * diag;
        const midX = room.x + dx * midDist;
        const midY = room.y + dy * midDist;
        const bandW = band.width * diag * 1.6;

        for (let i = steps; i >= 1; i--) {
            const t = i / steps;
            const w = bandW * t;
            const a = 65 * (1 - t) * (1 - t) * glassAmount;

            push();
            translate(midX, midY);
            rotate(angle - HALF_PI);
            fill(235, 238, 245, a);
            rect(0, 0, w, bandLen);
            pop();
        }

        push();
        translate(midX, midY);
        rotate(angle - HALF_PI);
        stroke(255, 255, 255, 140 * glassAmount);
        strokeWeight(3);
        line(0, -bandLen / 2, 0, bandLen / 2);
        stroke(255, 255, 255, 220 * glassAmount);
        strokeWeight(1);
        line(0, -bandLen / 2, 0, bandLen / 2);
        pop();
    }

    rectMode(CORNER);
    pop();
}

function drawRoomShading(room, vis) {
    noStroke();
    const edge = min(room.w, room.h) * 0.22;
    for (let i = 0; i < 8; i++) {
        const t = i / 8;
        const w = edge * (1 - t);
        const a = 45 * (1 - t) * vis;

        fill(0, 0, 0, a);
        rect(room.x, room.y, room.w, w);
        fill(0, 0, 0, a * 0.8);
        rect(room.x, room.y, w, room.h);

        fill(255, 255, 255, a * 0.7);
        rect(room.x, room.y + room.h - w, room.w, w);
        fill(255, 255, 255, a * 0.5);
        rect(room.x + room.w - w, room.y, w, room.h);
    }
}

function drawFurniture(room, alphaFactor) {
    const n = room.furniture.n;
    if (n == 0){
        return;
    }

    const slot = room.w / n;
    const s = min(room.h, slot) * 0.35;
    const floorY = room.y + room.h;

    stroke(60);
    strokeWeight(2);
    for (let i = 0; i < n; i++) {
        const cx = room.x + slot * (i + 0.5);
        const jitter = room.furniture.jitter[i];
        const cols = room.furniture.colors[i];

        push();
        translate(cx, floorY);
        rotate(radians(jitter));
        translate(2, 3);
        noStroke();
        fill(0, 0, 0, 45 * (alphaFactor));
        drawObject(room.type, 0, 0, s, true, cols, alphaFactor);
        pop();

        push();
        translate(cx, floorY);
        rotate(radians(jitter));
        stroke(60, 255 * alphaFactor);
        strokeWeight(2);
        drawObject(room.type, 0, 0, s, false, cols, alphaFactor);
        pop();
    }
}

function makeFurnitureState(room) {
    const n = room.type === "closet" ? 1 : floor(room.w / OBJECT_SPACING);
    const colors = [];
    const jitter = [];
    for (let i = 0; i < n; i++) {
        colors.push([randomColor(), randomColor(), randomColor()]);
        jitter.push(random(-2, 2));
    }
    return {n, colors, jitter};
}

//AI generated code for drawing furtniture in the rooms:
function drawObject(type, cx, floorY, s, silhouette, cols, alphaFactor) {
  const a = 255 * alphaFactor;
  let ci = 0;
  const setFill = () => {
    if (!silhouette) {
      const c = cols[ci++];
      fill(c[0], c[1], c[2], a);
    }
  };

  if (type === "bedroom") {
    setFill();
    rect(cx - s, floorY - s * 0.9, s * 0.15, s * 0.9);        // headboard
    setFill();
    rect(cx - s, floorY - s * 0.5, s * 2, s * 0.5, 4);        // mattress
    setFill();
    rect(cx - s * 0.8, floorY - s * 0.65, s * 0.5, s * 0.2, 4); // pillow
  } else if (type === "living") {
    setFill();
    rect(cx - s, floorY - s * 0.9, s * 2, s * 0.4, 6);        // couch back
    setFill();
    rect(cx - s, floorY - s * 0.55, s * 2, s * 0.55, 6);      // couch seat
  } else if (type === "kitchen") {
    setFill();
    rect(cx - s, floorY - s * 0.8, s * 2, s * 0.8);           // counter
    setFill();
    rect(cx - s * 0.6, floorY - s, s * 0.5, s * 0.2);         // pot
  } else if (type === "bath") {
    setFill();
    rect(cx - s, floorY - s * 0.5, s * 2, s * 0.5, s * 0.25); // tub
  } else if (type === "closet") {
    setFill();
    rect(cx - s * 0.7, floorY - s * 1.1, s * 1.4, s * 1.1, 3); // dresser body
    setFill();
    rect(cx - s * 0.55, floorY - s * 0.85, s * 1.1, s * 0.25, 2); // top drawer
    rect(cx - s * 0.55, floorY - s * 0.5, s * 1.1, s * 0.25, 2);  // bottom drawer
    setFill();
    circle(cx, floorY - s * 0.72, s * 0.07); // top handle
    circle(cx, floorY - s * 0.37, s * 0.07); // bottom handle
  }
}

function makePersonState(room) {
  const s = constrain(min(room.w, room.h) * 0.28, 12, 40);
  const maxHeightScale = constrain(room.h / (s * 2), 0.7, 1.4);
  const heightScale = random(0.7, maxHeightScale);
  const skin = randomColor();
  const shirt = randomColor();
  const pants = randomColor();

  const marginX = s * 0.8;
  const cx = random(room.x + marginX, room.x + room.w - marginX);

  return {s, heightScale, skin, shirt, pants, cx};
}

function drawPerson(room, alpha) {
  const {s, heightScale, skin, shirt, pants, cx}  = room.person;

  const floorY = room.y + room.h;
  const headR = s * 0.5 * heightScale;
  const bodyH = s * 1.3 * heightScale;
  const legY = floorY - s * 0.1;
  const bodyTopY = legY - bodyH;
  const headCy = bodyTopY - headR * 0.9;

  stroke(60, alpha);
  strokeWeight(2);

  const legH = s * 0.5 * heightScale;
  fill(pants[0], pants[1], pants[2], alpha);
  rect(cx - s * 0.28, legY - legH, s * 0.22, legH, 2);
  rect(cx + s * 0.06, legY - legH, s * 0.22, legH, 2);

  fill(shirt[0], shirt[1], shirt[2], alpha);
  rect(cx - s * 0.35, bodyTopY, s * 0.7, bodyH - s * 0.5 * heightScale, 4);

  const armH = s * 0.55 * heightScale;
  fill(skin[0], skin[1], skin[2], alpha);
  rect(cx - s * 0.5, bodyTopY + s * 0.1, s * 0.15, armH, 3);
  rect(cx + s * 0.35, bodyTopY + s * 0.1, s * 0.15, armH, 3);

  fill(skin[0], skin[1], skin[2], alpha);
  circle(cx, headCy, headR * 2);
}

function drawChimney() {
    const px = roof.x3 + (roof.x2 - roof.x3) * 0.6;
    const py = roof.y3 + (roof.y2 - roof.y3) * 0.6;
    const cw = house.w * 0.04;
    const top = py - roof.h * 0.25;
    fill(roof.chimneyCol);
    stroke(60);
    strokeWeight(3);
    rect(px, top, cw, py - top + roof.h * 0.3);
}

function drawAtticWindow() {
    fill(roof.windowCol);
    stroke(60);
    strokeWeight(3);
    circle(roof.x3, roof.y3 + roof.h * 0.6, roof.h * 0.3);
}