'use strict';

document.addEventListener('submit', (event) => {
    const form = event.target;
    if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
        event.preventDefault();
        return;
    }
    if (!form.checkValidity()) {
        event.preventDefault();
        form.reportValidity();
    }
});

document.querySelectorAll('[data-isbn]').forEach((input) => {
    input.addEventListener('input', () => {
        const value = input.value.trim();
        const valid = /^\d{13}$/.test(value) && [...value].reduce((sum, digit,
            index) => sum + Number(digit) * (index % 2 ? 3 : 1), 0) % 10 === 0;
        input.setCustomValidity(value && !valid ?
            'ISBN має містити 13 цифр і коректну контрольну цифру.' : '');
    });
});

document.querySelectorAll('[data-password-policy]').forEach((input) => {
    input.addEventListener('input', () => {
        const valid = input.value.length >= 8 && /\p{L}/u.test(input.value) && /\d/
            .test(input.value);
        input.setCustomValidity(valid ? '' :
            'Потрібно від 8 символів, щонайменше літера та цифра.');
    });
});

document.querySelector('[data-copy-token]')?.addEventListener('click', async (event) => {
    try {
        await navigator.clipboard.writeText(document.getElementById('api-token').value);
        event.target.textContent = 'Скопійовано ✓';
    } catch {
        const input = document.getElementById('api-token');
        input.type = 'text';
        input.select();
        event.target.textContent = 'Виділено для копіювання';
    }
});

const chartSource = document.getElementById('chart-data');
if (chartSource) {
    const data = JSON.parse(chartSource.textContent);
    const number = (value) => Number(value).toLocaleString('uk-UA', {
        maximumFractionDigits: 0
    });

    function responsiveCanvas(id, draw) {
        const canvas = document.getElementById(id);
        const height = Number(canvas.getAttribute('height'));

        function paint() {
            const width = canvas.parentElement.clientWidth;
            const dpr = window.devicePixelRatio || 1;
            canvas.width = Math.round(width * dpr);
            canvas.height = Math.round(height * dpr);
            canvas.style.height = height + 'px';
            const ctx = canvas.getContext('2d');
            ctx.scale(dpr, dpr);
            ctx.font = '11px "Segoe UI", sans-serif';
            draw(ctx, width, height);
        }
        new ResizeObserver(paint).observe(canvas.parentElement);
        paint();
    }
    responsiveCanvas('daily-chart', (ctx, width, height) => {
        const left = 60,
            right = width - 16,
            top = 25,
            bottom = height - 42;
        const max = Math.max(1, ...data.daily.map((r) => Number(r.revenue))) * 1.12;
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {
            const y = bottom - (bottom - top) * i / 4;
            ctx.strokeStyle = '#e9eee7';
            ctx.beginPath();
            ctx.moveTo(left, y);
            ctx.lineTo(right, y);
            ctx.stroke();
            ctx.fillStyle = '#839087';
            ctx.textAlign = 'right';
            ctx.fillText(number(max * i / 4), left - 10, y + 4);
        }
        const points = data.daily.map((row, i) => ({
            x: left + (right - left) * i / Math.max(1, data.daily.length - 1),
            y: bottom - Number(row.revenue) / max * (bottom - top),
            row
        }));
        ctx.beginPath();
        points.forEach((p, i) => i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y));
        ctx.strokeStyle = '#277b60';
        ctx.lineWidth = 2.5;
        ctx.stroke();
        ctx.lineTo(right, bottom);
        ctx.lineTo(left, bottom);
        ctx.closePath();
        const gradient = ctx.createLinearGradient(0, top, 0, bottom);
        gradient.addColorStop(0, '#c7dfd294');
        gradient.addColorStop(1, '#e5f0e50a');
        ctx.fillStyle = gradient;
        ctx.fill();
        points.forEach((p, i) => {
            ctx.fillStyle = '#277b60';
            ctx.beginPath();
            ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
            ctx.fill();
            if (i % 3 === 0 || i === points.length - 1) {
                ctx.fillStyle = '#839087';
                ctx.textAlign = 'center';
                ctx.fillText(p.row.day.slice(8, 10) + '.' + p.row.day.slice(5, 7), p
                    .x, bottom + 24);
            }
        });
    });
    responsiveCanvas('category-chart', (ctx, width, height) => {
        const rows = data.categories;
        const labelWidth = Math.min(165, width * .43),
            right = width - 62;
        const max = Math.max(1, ...rows.map((r) => Number(r.revenue)));
        const step = Math.min(32, (height - 18) / Math.max(1, rows.length));
        rows.forEach((row, i) => {
            const y = 12 + i * step,
                barWidth = Math.max(0, right - labelWidth) * Number(row.revenue) /
                max;
            ctx.fillStyle = '#748079';
            ctx.textAlign = 'left';
            let label = row.category_name;
            while (ctx.measureText(label).width > labelWidth - 14 && label.length >
                2) label = label.slice(0, -2) + '…';
            ctx.fillText(label, 0, y + 13);
            ctx.fillStyle = '#f0f4ed';
            ctx.fillRect(labelWidth, y, Math.max(0, right - labelWidth), 20);
            ctx.fillStyle = i % 2 ? '#90b69b' : '#3c8066';
            ctx.fillRect(labelWidth, y, barWidth, 20);
            ctx.fillStyle = '#53695b';
            ctx.fillText(number(row.revenue), right + 8, y + 14);
        });
    });
}
