<!--
From Uiverse.io by alexruix - https://uiverse.io/alexruix/fluffy-starfish-52
MIT License, Copyright (c) alexruix (Alex Ruiz)
-->
<template>
	<div class="starfish-loader" role="status" aria-label="Loading 3D preview">
		<div class="starfish-cell starfish-d-0" />
		<div class="starfish-cell starfish-d-1" />
		<div class="starfish-cell starfish-d-2" />

		<div class="starfish-cell starfish-d-1" />
		<div class="starfish-cell starfish-d-2" />

		<div class="starfish-cell starfish-d-2" />
		<div class="starfish-cell starfish-d-3" />

		<div class="starfish-cell starfish-d-3" />
		<div class="starfish-cell starfish-d-4" />
	</div>
</template>

<style scoped>
/* From Uiverse.io by alexruix - https://uiverse.io/alexruix/fluffy-starfish-52 (MIT License) */
.starfish-loader {
	--cell-size: 20px;
	--cell-spacing: 1.5px;
	--cells: 3;
	--total-size: calc(var(--cells) * (var(--cell-size) + 2 * var(--cell-spacing)));
	display: flex;
	flex-wrap: wrap;
	width: var(--total-size);
	height: var(--total-size);
}

.starfish-cell {
	flex: 0 0 var(--cell-size);
	margin: var(--cell-spacing);
	background-color: transparent;
	box-sizing: border-box;
	border-radius: 3px;
	animation: 1.5s starfish-ripple ease infinite;
}

.starfish-cell.starfish-d-1 {
	animation-delay: 100ms;
}

.starfish-cell.starfish-d-2 {
	animation-delay: 200ms;
}

.starfish-cell.starfish-d-3 {
	animation-delay: 300ms;
}

.starfish-cell.starfish-d-4 {
	animation-delay: 400ms;
}

.starfish-cell:nth-child(1) {
	--cell-color: #1f3a6b;
}

.starfish-cell:nth-child(2) {
	--cell-color: #1d4685;
}

.starfish-cell:nth-child(3) {
	--cell-color: #1b529e;
}

.starfish-cell:nth-child(4) {
	--cell-color: #1a62be;
}

.starfish-cell:nth-child(5) {
	--cell-color: #1a6fd4;
}

.starfish-cell:nth-child(6) {
	--cell-color: #2b80e2;
}

.starfish-cell:nth-child(7) {
	--cell-color: #3d92ef;
}

.starfish-cell:nth-child(8) {
	--cell-color: #5aa7f8;
}

.starfish-cell:nth-child(9) {
	--cell-color: #7cc0ff;
}

@keyframes starfish-ripple {
	0% {
		background-color: transparent;
	}

	30% {
		background-color: var(--cell-color);
	}

	60% {
		background-color: transparent;
	}

	100% {
		background-color: transparent;
	}
}
</style>

