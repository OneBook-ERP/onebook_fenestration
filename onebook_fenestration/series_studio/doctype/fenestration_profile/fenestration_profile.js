frappe.ui.form.on("Fenestration Profile", {
	refresh(frm) {
		render_profile_section_preview(frm);
	},
	dxf_file(frm) {
		render_profile_section_preview(frm);
	},
});

function clean_dxf_filename(dxfPath) {
	const raw = (dxfPath || "").split("/").pop() || "section.dxf";
	return raw.replace(/([0-9a-f]{6}){1,2}(\.dxf)$/i, "$2");
}

function render_profile_section_preview(frm) {
	const field = frm.fields_dict.section_preview;
	if (!field || !field.$wrapper) return;

	const doc = frm.doc;
	if (!doc.section_svg || !doc.width_mm || !doc.depth_mm) {
		field.$wrapper.html(`
			<div style="border:1px solid #e2e8f0;border-radius:12px;background:#f8fafc;padding:32px;text-align:center;color:#64748b;margin-bottom:8px;">
				<div style="font-size:15px;font-weight:600;color:#334155;margin-bottom:4px;">No DXF Section Attached</div>
				<div style="font-size:13px;">Attach a CAD <code>.dxf</code> file above and save the profile to compute and preview its cross-section geometry.</div>
			</div>
		`);
		return;
	}

	const state = frm._section_view_state || {
		showGrid: true,
		showDims: true,
		showCentroid: true,
	};
	frm._section_view_state = state;

	const dxfName = clean_dxf_filename(doc.dxf_file);
	const loops = count_svg_loops(doc.section_svg);
	const chambers = Math.max(0, loops - 1);
	const unitNote = (doc.section_warnings || "").includes("units_assumed_mm")
		? "Units read as mm"
		: "Units in mm";
	const loopNote = `${loops} closed loop${loops === 1 ? "" : "s"}${chambers > 0 ? ` (${chambers} chamber${chambers === 1 ? "" : "s"})` : ""}`;
	const weight = doc.use_computed_weight && doc.computed_kg_per_m ? doc.computed_kg_per_m : doc.kg_per_m;

	const svgMarkup = build_blueprint_svg(doc, state);

	field.$wrapper.html(`
		<div class="fen-section-inspector" style="border:1px solid #e2e8f0;border-radius:12px;background:#ffffff;padding:22px 24px;margin-bottom:8px;box-shadow:0 1px 2px rgba(15,23,42,0.03);">
			<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:16px;">
				<div style="min-width:0;flex:1;">
					<div style="font-size:16px;font-weight:700;color:#0f172a;line-height:1.35;">
						${frappe.utils.escape_html(doc.profile_name || doc.profile_code)}
						<span style="color:#64748b;font-weight:500;"> · ${frappe.utils.escape_html(dxfName)}</span>
					</div>
					<div style="font-size:13px;color:#64748b;margin-top:4px;">
						${unitNote} · ${loopNote} · Role: <strong style="color:#334155;text-transform:capitalize;">${frappe.utils.escape_html(doc.role || "—")}</strong>
					</div>
				</div>
				<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;flex-shrink:0;">
					<div style="display:inline-flex;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;background:#f8fafc;">
						<button type="button" data-action="toggle-grid" style="border:none;background:${state.showGrid ? "#e2e8f0" : "transparent"};padding:5px 12px;font-size:12px;font-weight:600;color:#334155;cursor:pointer;">Grid</button>
						<button type="button" data-action="toggle-dims" style="border:none;border-left:1px solid #e2e8f0;background:${state.showDims ? "#e2e8f0" : "transparent"};padding:5px 12px;font-size:12px;font-weight:600;color:#334155;cursor:pointer;">Dimensions</button>
						<button type="button" data-action="toggle-centroid" style="border:none;border-left:1px solid #e2e8f0;background:${state.showCentroid ? "#e2e8f0" : "transparent"};padding:5px 12px;font-size:12px;font-weight:600;color:#334155;cursor:pointer;">Centroid</button>
					</div>
					<span style="display:inline-flex;align-items:center;padding:5px 14px;border-radius:999px;background:#dcfce7;color:#15803d;font-size:12px;font-weight:600;">
						Parsed
					</span>
				</div>
			</div>

			<div style="border:1px solid #e2e8f0;border-radius:10px;background:#f8fafc;overflow:hidden;display:flex;align-items:center;justify-content:center;min-height:330px;position:relative;">
				${svgMarkup}
			</div>

			<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px 48px;margin-top:20px;padding-top:18px;border-top:1px solid #f1f5f9;">
				<div>
					<div style="font-size:12px;color:#64748b;margin-bottom:3px;">Section area</div>
					<div style="font-size:19px;font-weight:700;color:#0f172a;letter-spacing:-0.01em;">${format_num(doc.area_mm2, 1)} mm²</div>
				</div>
				<div>
					<div style="font-size:12px;color:#64748b;margin-bottom:3px;">Weight</div>
					<div style="font-size:19px;font-weight:700;color:#0f172a;letter-spacing:-0.01em;">${format_num(weight, 3)} kg/m</div>
				</div>
				<div>
					<div style="font-size:12px;color:#64748b;margin-bottom:3px;">Width × depth</div>
					<div style="font-size:19px;font-weight:700;color:#0f172a;letter-spacing:-0.01em;">${format_num(doc.width_mm, 1)} × ${format_num(doc.depth_mm, 1)}</div>
				</div>
				<div>
					<div style="font-size:12px;color:#64748b;margin-bottom:3px;">Perimeter</div>
					<div style="font-size:19px;font-weight:700;color:#0f172a;letter-spacing:-0.01em;">${format_num(doc.perimeter_mm, 1)} mm</div>
				</div>
				<div>
					<div style="font-size:12px;color:#64748b;margin-bottom:3px;">Ix / Iy</div>
					<div style="font-size:17px;font-weight:700;color:#0f172a;letter-spacing:-0.01em;">${format_num(doc.ix_mm4, 0)} / ${format_num(doc.iy_mm4, 0)} mm⁴</div>
				</div>
				<div>
					<div style="font-size:12px;color:#64748b;margin-bottom:3px;">Material</div>
					<div style="font-size:17px;font-weight:700;color:#0f172a;letter-spacing:-0.01em;">Al 6063-T6</div>
				</div>
			</div>
		</div>
	`);

	field.$wrapper.find("[data-action='toggle-grid']").on("click", () => {
		state.showGrid = !state.showGrid;
		render_profile_section_preview(frm);
	});
	field.$wrapper.find("[data-action='toggle-dims']").on("click", () => {
		state.showDims = !state.showDims;
		render_profile_section_preview(frm);
	});
	field.$wrapper.find("[data-action='toggle-centroid']").on("click", () => {
		state.showCentroid = !state.showCentroid;
		render_profile_section_preview(frm);
	});
}

function build_blueprint_svg(doc, state) {
	const w = Math.max(Number(doc.width_mm) || 10, 1);
	const h = Math.max(Number(doc.depth_mm) || 10, 1);
	const span = Math.max(w, h);

	const cw = 640;
	const ch = 310;
	const padL = state.showDims ? 72 : 44;
	const padR = 52;
	const padT = 26;
	const padB = state.showDims ? 54 : 30;
	const availW = cw - padL - padR;
	const availH = ch - padT - padB;

	const s = Math.min(availW / w, availH / h);
	const dw = w * s;
	const dh = h * s;
	const ox = padL + (availW - dw) / 2;
	const oy = padT + (availH - dh) / 2;

	const minorStepMm = span <= 35 ? 1 : span <= 80 ? 2 : 5;
	const minorPx = minorStepMm * s;
	const majorPx = minorPx * 5;
	const pathStroke = 1.5 / s;

	const dimGap = 14;
	const tick = 5;
	const fontSize = 12.5;
	const dimY = oy + dh + dimGap;
	const dimX = ox - dimGap;
	const vTextX = dimX - 13;
	const vTextY = oy + dh / 2;

	const centroid = estimate_svg_centroid(doc.section_svg, w, h);
	const cx = ox + centroid.x * s;
	const cy = oy + centroid.y * s;
	const gridId = `fen-grid-${(doc.name || "p").replace(/[^a-zA-Z0-9_-]/g, "")}`;

	return `
		<svg viewBox="0 0 ${cw} ${ch}" style="width:100%;height:320px;display:block;" xmlns="http://www.w3.org/2000/svg">
			<defs>
				<pattern id="${gridId}-minor" width="${minorPx.toFixed(3)}" height="${minorPx.toFixed(3)}" patternUnits="userSpaceOnUse" patternTransform="translate(${ox.toFixed(2)}, ${oy.toFixed(2)})">
					<path d="M ${minorPx.toFixed(3)} 0 L 0 0 0 ${minorPx.toFixed(3)}" fill="none" stroke="#e2e8f0" stroke-width="0.7" />
				</pattern>
				<pattern id="${gridId}-major" width="${majorPx.toFixed(3)}" height="${majorPx.toFixed(3)}" patternUnits="userSpaceOnUse" patternTransform="translate(${ox.toFixed(2)}, ${oy.toFixed(2)})">
					<rect width="${majorPx.toFixed(3)}" height="${majorPx.toFixed(3)}" fill="url(#${gridId}-minor)" />
					<path d="M ${majorPx.toFixed(3)} 0 L 0 0 0 ${majorPx.toFixed(3)}" fill="none" stroke="#cbd5e1" stroke-width="1.1" />
				</pattern>
			</defs>

			${state.showGrid ? `<rect x="0" y="0" width="${cw}" height="${ch}" fill="url(#${gridId}-major)" />` : ""}

			<g transform="translate(${ox.toFixed(2)}, ${oy.toFixed(2)}) scale(${s.toFixed(4)})">
				<path d="${doc.section_svg}" fill="#94a3b8" fill-opacity="0.85" stroke="#1e293b" stroke-width="${pathStroke.toFixed(3)}" stroke-linejoin="round" fill-rule="evenodd" />
			</g>

			${
				state.showDims
					? `
				<g stroke="#475569" stroke-width="1.15" stroke-linecap="square">
					<line x1="${ox.toFixed(2)}" y1="${dimY.toFixed(2)}" x2="${(ox + dw).toFixed(2)}" y2="${dimY.toFixed(2)}" />
					<line x1="${ox.toFixed(2)}" y1="${(dimY - tick).toFixed(2)}" x2="${ox.toFixed(2)}" y2="${(dimY + tick).toFixed(2)}" />
					<line x1="${(ox + dw).toFixed(2)}" y1="${(dimY - tick).toFixed(2)}" x2="${(ox + dw).toFixed(2)}" y2="${(dimY + tick).toFixed(2)}" />

					<line x1="${dimX.toFixed(2)}" y1="${oy.toFixed(2)}" x2="${dimX.toFixed(2)}" y2="${(oy + dh).toFixed(2)}" />
					<line x1="${(dimX - tick).toFixed(2)}" y1="${oy.toFixed(2)}" x2="${(dimX + tick).toFixed(2)}" y2="${oy.toFixed(2)}" />
					<line x1="${(dimX - tick).toFixed(2)}" y1="${(oy + dh).toFixed(2)}" x2="${(dimX + tick).toFixed(2)}" y2="${(oy + dh).toFixed(2)}" />
				</g>
				<text x="${(ox + dw / 2).toFixed(2)}" y="${(dimY + 18).toFixed(2)}" text-anchor="middle" fill="#0f172a" font-size="${fontSize}" font-weight="600" font-family="Inter, system-ui, sans-serif">${Number(doc.width_mm).toFixed(1)}</text>
				<text x="${vTextX.toFixed(2)}" y="${vTextY.toFixed(2)}" text-anchor="middle" dominant-baseline="central" fill="#0f172a" font-size="${fontSize}" font-weight="600" font-family="Inter, system-ui, sans-serif" transform="rotate(-90 ${vTextX.toFixed(2)} ${vTextY.toFixed(2)})">${Number(doc.depth_mm).toFixed(1)}</text>
			`
					: ""
			}

			${
				state.showCentroid
					? `
				<g>
					<circle cx="${cx.toFixed(2)}" cy="${cy.toFixed(2)}" r="3.4" fill="#2563eb" stroke="#ffffff" stroke-width="1.2" />
					<text x="${(cx + 6.5).toFixed(2)}" y="${(cy - 2.5).toFixed(2)}" fill="#2563eb" stroke="#f8fafc" stroke-width="3" paint-order="stroke" font-size="11.5" font-weight="600" font-family="Inter, system-ui, sans-serif">centroid</text>
				</g>
			`
					: ""
			}
		</svg>
	`;
}

function count_svg_loops(svgPath) {
	if (!svgPath) return 0;
	const matches = svgPath.match(/M\s/g);
	return matches ? matches.length : 1;
}

function estimate_svg_centroid(svgPath, fallbackW, fallbackH) {
	if (!svgPath) return { x: fallbackW / 2, y: fallbackH / 2 };
	const subpaths = svgPath.split("Z").map((s) => s.trim()).filter(Boolean);
	let totalArea = 0;
	let cxSum = 0;
	let cySum = 0;
	let maxAbsArea = 0;

	const parsedLoops = subpaths.map((sub) => {
		const cleaned = sub.replace(/^M\s*/, "");
		const pairs = cleaned.split(/\s*L\s*/);
		const pts = [];
		for (const p of pairs) {
			const parts = p.trim().split(/\s+/);
			if (parts.length >= 2) {
				const x = parseFloat(parts[0]);
				const y = parseFloat(parts[1]);
				if (!Number.isNaN(x) && !Number.isNaN(y)) pts.push([x, y]);
			}
		}
		let area2 = 0;
		let sx = 0;
		let sy = 0;
		for (let i = 0; i < pts.length; i++) {
			const [x1, y1] = pts[i];
			const [x2, y2] = pts[(i + 1) % pts.length];
			const cross = x1 * y2 - x2 * y1;
			area2 += cross;
			sx += (x1 + x2) * cross;
			sy += (y1 + y2) * cross;
		}
		const absA = Math.abs(area2) / 2;
		if (absA > maxAbsArea) maxAbsArea = absA;
		return { absA, cx: area2 !== 0 ? sx / (3 * area2) : fallbackW / 2, cy: area2 !== 0 ? sy / (3 * area2) : fallbackH / 2 };
	});

	for (const loop of parsedLoops) {
		if (loop.absA <= 1e-6) continue;
		const sign = Math.abs(loop.absA - maxAbsArea) < 1e-4 ? 1 : -1;
		totalArea += sign * loop.absA;
		cxSum += sign * loop.absA * loop.cx;
		cySum += sign * loop.absA * loop.cy;
	}

	if (Math.abs(totalArea) > 1e-4) {
		const cx = cxSum / totalArea;
		const cy = cySum / totalArea;
		if (cx >= 0 && cx <= fallbackW && cy >= 0 && cy <= fallbackH) {
			return { x: cx, y: cy };
		}
	}
	return { x: fallbackW / 2, y: fallbackH / 2 };
}

function format_num(val, decimals) {
	if (val == null || val === "" || Number.isNaN(Number(val))) return "—";
	return Number(val).toLocaleString("en-IN", {
		minimumFractionDigits: decimals,
		maximumFractionDigits: decimals,
	});
}
