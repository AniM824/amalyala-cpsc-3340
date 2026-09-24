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

let house;
let roof;
let rooms = [];

function setup() {
    createCanvas(windowWidth, windowHeight);
    noCursor();
    noLoop();
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
    redraw();
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
        house = {x: x, y: y + roofH, w: size, h: size - roofH};
        rooms.push({ ...house, type: "living", col: randomColor() });
        return;
    }

    const roofH = constrain(availW * 0.3, MIN_FLOOR_H, availH / 3);
    house = { x: BORDER, y: BORDER + roofH, w: availW, h: availH - roofH };
    roof = { x1: house.x, y1: house.y, x2: house.x + house.w, y2: house.y, x3: house.x + house.w / 2, y3: BORDER, h: roofH };

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
    fill(randomColor());
    stroke(60);
    strokeWeight(3);
    triangle(roof.x1, roof.y1, roof.x2, roof.y2, roof.x3, roof.y3);
}

function drawRooms() {
    for (const room of rooms) {
        drawRoom(room);
    }
}

function drawRoom(room) {
    const shadowOffset = 5;
    noStroke();
    fill(0, 0, 0, 35);
    rect(room.x + shadowOffset, room.y + shadowOffset, room.w, room.h);

    fill(room.col);
    stroke(60);
    strokeWeight(3);
    rect(room.x, room.y, room.w, room.h);

    drawRoomShading(room);
    drawFurniture(room);
    drawPerson(room);
}

function drawRoomShading(room) {
    noStroke();
    const edge = min(room.w, room.h) * 0.22;
    for (let i = 0; i < 8; i++) {
        const t = i / 8;
        const w = edge * (1 - t);
        const a = 45 * (1 - t);

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

function drawFurniture(room) {
    if (room.type === "closet") {
        let n = 1;
    } else {
        let n = floor(room.w / OBJECT_SPACING);
    }
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
        const jitter = random(-2, 2);

        push();
        translate(cx, floorY);
        rotate(radians(jitter));
        translate(2, 3);
        noStroke();
        fill(0, 0, 0, 45);
        drawObject(room.type, 0, 0, s, true);
        pop();

        push();
        translate(cx, floorY);
        rotate(radians(jitter));
        stroke(60);
        strokeWeight(2);
        drawObject(room.type, 0, 0, s, false);
        pop();
    }
}

//AI generated code for drawing furtniture in the rooms:
function drawObject(type, cx, floorY, s, silhouette) {
  const setFill = () => { if (!silhouette) fill(randomColor()); };

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

function drawPerson(room) {
  const s = constrain(min(room.w, room.h) * 0.28, 12, 40);
  const maxHeightScale = constrain(room.h / (s * 2), 0.7, 1.4);
  const heightScale = random(0.7, maxHeightScale);
  const skin = randomColor();
  const shirt = randomColor();

  const furnitureCols = floor(room.w / OBJECT_SPACING);
  const marginX = s * 0.8;
  let cx;
  if (furnitureCols > 0) {
    const slot = room.w / furnitureCols;
    const slotIndex = floor(random(furnitureCols + 1));
    cx = room.x + slot * slotIndex;
    cx = constrain(cx, room.x + marginX, room.x + room.w - marginX);
  }
  else {
    cx = random(room.x + marginX, room.x + room.w - marginX);
  }

  const floorY = room.y + room.h;
  const headR = s * 0.5 * heightScale;
  const bodyH = s * 1.3 * heightScale;
  const legY = floorY - s * 0.1;
  const bodyTopY = legY - bodyH;
  const headCy = bodyTopY - headR * 0.9;

  stroke(60);
  strokeWeight(2);

  //AI generated code for drawing a person:
  // legs
  const legH = s * 0.5 * heightScale;
  fill(randomColor());
  rect(cx - s * 0.28, legY - legH, s * 0.22, legH, 2);
  rect(cx + s * 0.06, legY - legH, s * 0.22, legH, 2);

  // body
  fill(shirt);
  rect(cx - s * 0.35, bodyTopY, s * 0.7, bodyH - s * 0.5 * heightScale, 4);

  // arms
  const armH = s * 0.55 * heightScale;
  fill(skin);
  rect(cx - s * 0.5, bodyTopY + s * 0.1, s * 0.15, armH, 3);
  rect(cx + s * 0.35, bodyTopY + s * 0.1, s * 0.15, armH, 3);

  // head
  fill(skin);
  circle(cx, headCy, headR * 2);
}

function drawChimney() {
    const px = roof.x3 + (roof.x2 - roof.x3) * 0.6;
    const py = roof.y3 + (roof.y2 - roof.y3) * 0.6;
    const cw = house.w * 0.04;
    const top = py - roof.h * 0.25;
    fill(randomColor());
    stroke(60);
    strokeWeight(3);
    rect(px, top, cw, py - top + roof.h * 0.3);
}

function drawAtticWindow() {
    fill(randomColor());
    stroke(60);
    strokeWeight(3);
    circle(roof.x3, roof.y3 + roof.h * 0.6, roof.h * 0.3);
}