"""Publication figures from the single recalculated metrics snapshot."""
import json
from collections import Counter

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.transforms import Bbox
from PIL import Image

from study import ROOT, GROUPS, CODES, LEVEL_NAMES, read_json, write_json, sha256

BLUE, ORANGE, INK, GRID = '#2764C5', '#DC7B29', '#1B2738', '#DEE5EF'
GC = dict(zip(GROUPS, ['#25754C', '#7553A8', '#BD4F52', '#16877F']))
LC = ['#3668A0', '#B5BDC6', '#A07EB5', '#DD9846', '#288A88', '#BB5E69', '#879B50']
SC = ['#A83444', '#D67D53', '#D4B855', '#6BA080', '#357663']
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12,
    'text.color': INK, 'axes.labelcolor': INK, 'xtick.color': '#526075',
    'ytick.color': '#526075', 'svg.fonttype': 'none', 'svg.hashsalt': 'guilt-appeal-research',
    'savefig.facecolor': 'white', 'pdf.fonttype': 42})


def fmt(x, n=2):
    return f'{x:.{n}f}'.replace('.', ',')


def axes_style(ax):
    ax.set_axisbelow(True)
    ax.grid(axis='y', color=GRID, lw=.8)
    ax.tick_params(length=0, pad=8)
    for side in ('top', 'right', 'left'):
        ax.spines[side].set_visible(False)
    ax.spines['bottom'].set_color('#B9C3D0')


def base(title, width=13, height=7.5):
    fig, ax = plt.subplots(figsize=(width, height), facecolor='white')
    fig.subplots_adjust(left=.09, right=.97, bottom=.16, top=.78)
    fig.text(.09, .95, title, fontsize=19, weight='bold', va='top')
    axes_style(ax)
    return fig, ax


def labels(ax, bars, digits=0):
    for bar in bars:
        ax.annotate(fmt(bar.get_height(), digits),
                    (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 5), textcoords='offset points', ha='center', fontsize=11, weight='bold')


def rater_legend(ax):
    ax.legend(handles=[Patch(color=BLUE, label='LLM'), Patch(color=ORANGE, label='Человек')],
              loc='lower left', bbox_to_anchor=(0, 1.04), frameon=False, ncol=2)


def group_legend(fig, y=.87):
    fig.legend(handles=[Patch(color=GC[g], label='К — контрольная' if g == 'К' else 'Группа ' + g) for g in GROUPS],
               loc='upper left', bbox_to_anchor=(.085, y), ncol=4, frameon=False)


def build():
    data = read_json(ROOT / '06_results/summary.json')
    rows, groups = data['records'], data['groups']
    ordered = [r for g in GROUPS for r in rows if r['group'] == g]
    out = ROOT / '06_results/figures'
    books, manifest = {}, []
    for kind in ('nat', 'guilt', 'fld_freq'):
        (out / kind / 'png').mkdir(parents=True, exist_ok=True)
        (out / kind / 'svg').mkdir(exist_ok=True)
        books[kind] = PdfPages(out / kind / 'all_figures.pdf', metadata={'Title': kind.upper(),
                                  'CreationDate': None, 'ModDate': None})

    def save(fig, kind, name, title, note):
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        for artist in fig.findobj(matplotlib.text.Text):
            if artist.get_visible() and artist.get_text():
                box = artist.get_window_extent(renderer)
                if box.x0 < -2 or box.y0 < -2 or box.x1 > fig.bbox.width + 2 or box.y1 > fig.bbox.height + 2:
                    raise ValueError(f'{name}: text outside canvas: {artist.get_text()}')
        paths = {}
        for ext in ('png', 'svg'):
            path = out / kind / ext / f'{name}.{ext}'
            fig.savefig(path, dpi=220, metadata={'Date': None} if ext == 'svg' else None)
            if ext == 'svg':
                path.write_text(path.read_text(encoding='utf-8'), encoding='utf-8', newline='\n')
            paths[ext] = path.relative_to(ROOT).as_posix()
        with Image.open(ROOT / paths['png']) as im:
            im.verify()
        books[kind].savefig(fig)
        plt.close(fig)
        manifest.append({'collection': kind, 'id': name, 'title': title, 'caption': note,
                         **paths, 'sha256': {e: sha256(ROOT / p) for e, p in paths.items()}})

    # NAT 1: total distribution.
    title = 'Распределение оценок естественности диалогов'
    fig, ax = base(title)
    x = np.arange(1, 6)
    for who, offset, color in [('llm', -.18, BLUE), ('human', .18, ORANGE)]:
        counts = [sum(r[f'NAT_{who}'] == s for r in rows) for s in x]
        labels(ax, ax.bar(x + offset, counts, .33, color=color))
    ax.set(xticks=x, ylim=(0, 16), yticks=range(0, 17, 2), xlabel='Индекс естественности NAT', ylabel='Количество диалогов')
    rater_legend(ax)
    save(fig, 'nat', '01_score_distribution', title, 'Число диалогов с каждым баллом NAT; по 24 оценки каждого оценщика.')

    # NAT 2: group distributions.
    title = 'Распределение NAT по группам диалогов'
    fig, axs = plt.subplots(2, 2, figsize=(13, 10), facecolor='white')
    fig.subplots_adjust(left=.08, right=.97, bottom=.09, top=.81, hspace=.55, wspace=.24)
    fig.text(.08, .96, title, fontsize=20, weight='bold', va='top')
    fig.legend(handles=[Patch(color=BLUE, label='LLM'), Patch(color=ORANGE, label='Человек')],
               bbox_to_anchor=(.08, .92), loc='upper left', frameon=False, ncol=2)
    for g, ax in zip(GROUPS, axs.flat):
        subset = [r for r in rows if r['group'] == g]
        for who, offset, color in [('llm', -.18, BLUE), ('human', .18, ORANGE)]:
            bars = ax.bar(x + offset, [sum(r[f'NAT_{who}'] == s for r in subset) for s in x], .33, color=color)
            labels(ax, bars)
        axes_style(ax)
        ax.set(title='Контрольная группа К' if g == 'К' else 'Группа ' + g,
               xticks=x, ylim=(0, 6.2), yticks=range(7), xlabel='NAT', ylabel='Количество диалогов')
    save(fig, 'nat', '02_group_distributions', title, 'Абсолютные частоты оценок NAT; шесть диалогов в каждой группе.')

    # NAT 3: proportions.
    title = 'Доли оценок естественности по группам'
    fig, ax = base(title, height=8.5)
    y, ticklabels = np.arange(8), []
    bottoms = np.zeros(8)
    for score in range(1, 6):
        values = [100 * groups[g]['nat_distribution'][who][str(score)] / groups[g]['n']
                  for g in GROUPS for who in ('llm', 'human')]
        ax.barh(y, values, left=bottoms, color=SC[score - 1], label=str(score), height=.72)
        for yi, left, value in zip(y, bottoms, values):
            if value:
                ax.text(left + value / 2, yi, fmt(value, 1) + '%', ha='center', va='center', fontsize=10, color='white' if score in (1, 5) else INK)
        bottoms += values
    ticklabels = [f'{g} · {name}' for g in GROUPS for name in ('LLM', 'Человек')]
    ax.set(yticks=y, yticklabels=ticklabels, xlim=(0, 100), xlabel='Доля диалогов, %')
    ax.invert_yaxis(); ax.grid(False)
    ax.legend(title='Балл NAT', bbox_to_anchor=(0, 1.03), loc='lower left', ncol=5, frameon=False)
    save(fig, 'nat', '03_group_proportions', title, 'Распределение порядковых баллов; проценты рассчитаны отдельно для каждой группы и оценщика.')

    # NAT 4: score agreement matrix.
    title = 'Совпадения и расхождения оценок NAT'
    fig, ax = base(title)
    matrix = np.array([[sum(r['NAT_human'] == h and r['NAT_llm'] == m for r in rows) for m in range(1, 6)] for h in range(1, 6)])
    ax.grid(False)
    im = ax.imshow(matrix, origin='lower', cmap='Blues', vmin=0, vmax=max(1, matrix.max()))
    for h in range(5):
        for m in range(5):
            ax.text(m, h, str(matrix[h, m]), ha='center', va='center', color='white' if matrix[h, m] > matrix.max() / 2 else INK, fontsize=15)
    ax.set(xticks=range(5), xticklabels=range(1, 6), yticks=range(5), yticklabels=range(1, 6), xlabel='Оценка LLM', ylabel='Оценка человека')
    fig.colorbar(im, ax=ax, label='Количество диалогов')
    save(fig, 'nat', '04_agreement_matrix', title, 'Ячейка показывает число диалогов с соответствующей парой оценок.')

    # NAT 5: paired ratings by dialogue, in numeric order.
    title = 'Парные оценки естественности по диалогам'
    fig, ax = base(title, width=15)
    for i, r in enumerate(rows):
        ax.plot([i, i], [r['NAT_llm'], r['NAT_human']], color='#AAB6C3', lw=1.5)
    ax.scatter(range(len(rows)), [r['NAT_llm'] for r in rows], c=BLUE, s=45, zorder=3)
    ax.scatter(range(len(rows)), [r['NAT_human'] for r in rows], facecolors='none', edgecolors=ORANGE, marker='s', s=90, linewidths=1.7, zorder=4)
    ax.set(xticks=range(len(rows)), xticklabels=[r['dialogue_id'] for r in rows], yticks=range(1, 6), ylim=(.7, 5.35), ylabel='NAT')
    plt.setp(ax.get_xticklabels(), rotation=55, ha='right')
    rater_legend(ax)
    save(fig, 'nat', '05_paired_ratings', title, 'Линия соединяет две оценки одного диалога. Круг — LLM; контурный квадрат — человек.')

    # NAT 6: distribution of differences.
    title = 'Разности оценок естественности'
    fig, ax = base(title)
    differences = Counter(r['NAT_human'] - r['NAT_llm'] for r in rows)
    keys = list(range(min(differences), max(differences) + 1))
    bars = ax.bar(keys, [differences[k] for k in keys], color=[BLUE if k < 0 else ORANGE if k > 0 else '#8793A4' for k in keys], width=.65)
    labels(ax, bars)
    ax.set(xticks=keys, xticklabels=[f'{k:+d}' if k else '0' for k in keys], ylim=(0, 10), ylabel='Количество диалогов', xlabel='NAT человека − NAT модели')
    ax.legend(handles=[Patch(color=BLUE, label='Выше у LLM'), Patch(color='#8793A4', label='Совпадение'), Patch(color=ORANGE, label='Выше у человека')],
              loc='lower left', bbox_to_anchor=(0, 1.04), ncol=3, frameon=False)
    save(fig, 'nat', '06_rating_differences', title, 'Знак разности отражает направление расхождения; ноль означает точное совпадение.')

    # NAT 7: all observations and medians.
    title = 'Индивидуальные оценки и медианы NAT'
    fig, ax = base(title)
    for i, group in enumerate(GROUPS):
        for who, offset, color, marker in [('llm', -.19, BLUE, 'o'), ('human', .19, ORANGE, 'D')]:
            values = [r[f'NAT_{who}'] for r in rows if r['group'] == group]
            for score, n in Counter(values).items():
                xs = i + offset + (np.arange(n) - (n - 1) / 2) * .05
                ax.scatter(xs, [score] * n, color=color, marker=marker, s=45)
            median = groups[group][f'NAT_{who}']['median']
            ax.plot([i + offset - .13, i + offset + .13], [median, median], color=color, lw=3)
    ax.set(xticks=range(4), xticklabels=GROUPS, yticks=range(1, 6), ylim=(.6, 5.4), ylabel='NAT', xlabel='Группа диалогов')
    rater_legend(ax)
    save(fig, 'nat', '07_observations_and_medians', title, 'Точки — отдельные диалоги; горизонтальные отрезки — медианы соответствующего оценщика.')

    # NAT 8: mean scores.
    title = 'Средняя естественность диалогов по группам'
    fig, ax = base(title)
    for who, offset, color in [('llm', -.18, BLUE), ('human', .18, ORANGE)]:
        bars = ax.bar(np.arange(4) + offset, [groups[g][f'NAT_{who}']['mean'] for g in GROUPS], .33, color=color)
        labels(ax, bars, 2)
    ax.set(xticks=range(4), xticklabels=GROUPS, ylim=(0, 5), yticks=range(6), ylabel='Средний балл NAT', xlabel='Группа диалогов')
    rater_legend(ax)
    save(fig, 'nat', '08_group_means', title, 'Описательные средние порядковых баллов; вывод о статистической значимости не делается.')

    # NAT 9: clean grouped line chart, preserving group label colors.
    title = 'Оценки естественности по группам диалогов'
    fig, ax = base(title, width=16, height=8)
    fig.subplots_adjust(bottom=.28)
    x = np.arange(len(ordered))
    for i, g in enumerate(GROUPS):
        ax.axvspan(i * 6 - .5, i * 6 + 5.5, color=GC[g], alpha=.06)
        ax.text(i * 6 + 2.5, -.25, 'Контрольная (К)' if g == 'К' else 'Группа ' + g,
                transform=ax.get_xaxis_transform(), ha='center', va='top', color=GC[g], weight='bold')
    ax.plot(x, [r['NAT_llm'] for r in ordered], color=BLUE, marker='o', lw=2.2)
    ax.plot(x, [r['NAT_human'] for r in ordered], color=ORANGE, marker='s', mfc='none', ms=8, ls='--', lw=1.8)
    ax.set(xticks=x, xticklabels=[r['dialogue_id'] for r in ordered], yticks=range(1, 6), ylim=(.7, 5.3), ylabel='NAT', xlim=(-.5, 23.5))
    for tick, row in zip(ax.get_xticklabels(), ordered):
        tick.set_color(GC[row['group']]); tick.set_weight('bold'); tick.set_rotation(55); tick.set_ha('right')
    rater_legend(ax)
    save(fig, 'nat', '09_grouped_lines', title, 'Диалоги упорядочены по группам К, А, Б, В. Цвет подписей обозначает группу; линии — оценщика.')

    # GUILT 1: reference and model by group.
    title = 'Наличие апелляции к вине по группам'
    fig, ax = base(title)
    for who, offset, color in [('llm', -.18, BLUE), ('human', .18, ORANGE)]:
        values = [100 * groups[g][f'guilt_positive_{who}'] / groups[g]['n'] for g in GROUPS]
        labels(ax, ax.bar(np.arange(4) + offset, values, .33, color=color), 0)
    ax.set(xticks=range(4), xticklabels=GROUPS, ylim=(0, 118), yticks=range(0, 101, 20), ylabel='Диалоги с GUILT = 1, %', xlabel='Группа диалогов')
    rater_legend(ax)
    save(fig, 'guilt', '01_group_comparison', title, 'Человеческая метка задана автором по группе; машинная оценка сохранена без подмены эталоном.')

    # GUILT 2: confusion matrix and diagnostic measures.
    title = 'Согласованность оценки GUILT с человеческим эталоном'
    fig, axs = plt.subplots(1, 2, figsize=(14, 7.5), gridspec_kw={'width_ratios': [1, 1.45]}, facecolor='white')
    fig.subplots_adjust(left=.08, right=.97, bottom=.18, top=.78, wspace=.48)
    fig.text(.08, .95, title, fontsize=19, weight='bold', va='top')
    p = data['overall']['guilt_performance']; ax = axs[0]
    mat = np.array([[p['TN'], p['FP']], [p['FN'], p['TP']]])
    ax.imshow(mat, cmap='Blues', vmin=0, vmax=max(1, mat.max()))
    for h in range(2):
        for m in range(2):
            ax.text(m, h, str(mat[h, m]), ha='center', va='center', fontsize=24, color='white' if mat[h, m] > mat.max() / 2 else INK)
    ax.set(xticks=[0, 1], xticklabels=['Нет (0)', 'Есть (1)'], yticks=[0, 1], yticklabels=['Нет (0)', 'Есть (1)'], xlabel='LLM', ylabel='Человеческий эталон')
    ax = axs[1]; axes_style(ax)
    names = ['Accuracy', 'Чувствительность', 'Специфичность', 'Balanced accuracy']
    vals = [100 * p[k] for k in ('accuracy', 'sensitivity', 'specificity', 'balanced_accuracy')]
    bars = ax.barh(range(4), vals, color=[BLUE, GC['К'], '#BD4F52', '#7553A8'], height=.6)
    for i, val in enumerate(vals):
        ax.text(val + 2, i, fmt(val, 1) + '%', va='center', fontsize=12)
    ax.set(yticks=range(4), yticklabels=names, xlim=(0, 120), xticks=range(0, 101, 25), xlabel='%')
    ax.invert_yaxis()
    save(fig, 'guilt', '02_confusion_and_performance', title, 'Результаты относительно принятого группового эталона; расхождения: D015, D018, D024.')

    # FLD/FREQ 1: group means, with actual observations.
    title = 'Разнообразие и частотность средств апелляции к вине'
    fig, axs = plt.subplots(1, 2, figsize=(14, 8), facecolor='white')
    fig.subplots_adjust(left=.08, right=.97, bottom=.14, top=.73, wspace=.25)
    fig.text(.08, .95, title, fontsize=20, weight='bold', va='top'); group_legend(fig)
    for key, ax in zip(('FLD', 'FREQ'), axs):
        bars = ax.bar(range(4), [groups[g][key]['mean'] for g in GROUPS], color=[GC[g] for g in GROUPS], width=.6)
        for i, g in enumerate(GROUPS):
            vals = [r[key] for r in ordered if r['group'] == g]
            ax.scatter(i + np.linspace(-.17, .17, len(vals)), vals, color=INK, s=22, zorder=3)
            if g == 'К':
                ax.annotate(fmt(groups[g][key]['mean']), (i, bars[i].get_height()),
                            xytext=(0, 9), textcoords='offset points', ha='center', weight='bold')
            else:
                ax.text(i, bars[i].get_height() * .25, fmt(groups[g][key]['mean']), color='white', ha='center', weight='bold')
        axes_style(ax); ax.set(xticks=range(4), xticklabels=GROUPS, ylabel=key, ylim=(0, 15 if key == 'FLD' else 56))
    save(fig, 'fld_freq', '01_group_means', title, 'Столбцы — средние, точки — отдельные диалоги. Подсчёт по сохранённым occurrences модели, включая вложенные реализации.')

    # FLD/FREQ 2: dialogue counts.
    title = 'FLD и FREQ по всем диалогам'
    fig, axs = plt.subplots(2, 1, figsize=(16, 10), sharex=True, facecolor='white')
    fig.subplots_adjust(left=.08, right=.98, bottom=.15, top=.8, hspace=.25)
    fig.text(.08, .96, title, fontsize=21, weight='bold', va='top'); group_legend(fig, .91)
    for key, ax in zip(('FLD', 'FREQ'), axs):
        ax.bar(range(24), [r[key] for r in ordered], color=[GC[r['group']] for r in ordered])
        axes_style(ax); ax.set_ylabel(key)
    axs[0].set_ylim(0, 15); axs[1].set_xticks(range(24), [r['dialogue_id'] for r in ordered], rotation=55, ha='right')
    save(fig, 'fld_freq', '02_dialogue_metrics', title, 'Порядок групп: К, А, Б, В; исходные машинные реализации сохранены и при расхождении по GUILT.')

    # FLD/FREQ 3: code coverage and totals.
    title = 'Представленность категорий G01–G15'
    fig, axs = plt.subplots(2, 1, figsize=(15, 10), sharex=True, facecolor='white')
    fig.subplots_adjust(left=.09, right=.98, bottom=.13, top=.86, hspace=.32)
    fig.text(.09, .96, title, fontsize=21, weight='bold', va='top')
    for key, ax, color, ylabel in [('dialogues_present', axs[0], BLUE, 'Диалогов с категорией'), ('frequency', axs[1], ORANGE, 'Размеченных реализаций')]:
        vals = [sum(r[key] for r in data['categories'] if r['code'] == c) for c in CODES]
        bars = ax.bar(range(15), vals, color=color, width=.7); labels(ax, bars)
        axes_style(ax); ax.set_ylabel(ylabel); ax.set_ylim(0, max(vals) * 1.2)
    axs[1].set_xticks(range(15), CODES)
    save(fig, 'fld_freq', '03_category_coverage_and_frequency', title, 'Охват диалогов и количество реализаций — разные единицы; G14 означает речевые акты, G15 — многоходовые последовательности.')

    # FLD/FREQ 4: levels.
    title = 'Языковые уровни в структуре размеченных реализаций'
    fig, ax = base(title, width=15, height=9)
    fig.subplots_adjust(bottom=.3, top=.83)
    bottom = np.zeros(4)
    for level, color in zip(LEVEL_NAMES, LC):
        values = [100 * sum(r['frequency'] for r in data['levels'] if r['group'] == g and r['level'] == level) / groups[g]['FREQ_total'] for g in GROUPS]
        ax.bar(range(4), values, bottom=bottom, color=color, label=level, width=.62)
        bottom += values
    ax.set(xticks=range(4), xticklabels=GROUPS, ylim=(0, 100), ylabel='Доля в FREQ группы, %')
    ax.legend(loc='upper center', bbox_to_anchor=(.5, -.13), ncol=2, frameon=False, fontsize=11)
    save(fig, 'fld_freq', '04_language_levels', title, 'Доли уровней рассчитаны по числу записей occurrences; вложенные коды входят в подсчёт как отдельные реализации.')

    # FLD/FREQ 5: diversity-frequency relation.
    title = 'Соотношение разнообразия и частотности'
    fig, ax = base(title, width=14, height=8)
    group_legend(fig)
    for g in GROUPS:
        subset = [r for r in rows if r['group'] == g]
        ax.scatter([r['FLD'] for r in subset], [r['FREQ'] for r in subset],
                   color=GC[g], marker='s' if g == 'А' else 'o', s=90 if g == 'А' else 58, alpha=.8, zorder=3)
    # Separate labels for coincident observations without moving the observations.
    grouped = {}
    for r in rows:
        grouped.setdefault((r['FLD'], r['FREQ']), []).append(r['dialogue_id'])
    ax.set(xlim=(-.6, 15), ylim=(-3, 57), xticks=range(0, 16), xlabel='FLD — число разных категорий', ylabel='FREQ — число реализаций')
    fig.canvas.draw()
    renderer, placed = fig.canvas.get_renderer(), []
    point_boxes = []
    for point in grouped:
        px, py = ax.transData.transform(point)
        point_boxes.append(Bbox.from_extents(px - 5, py - 5, px + 5, py + 5))
    offsets = [(8, 6), (8, -15), (-8, 6), (-8, -15), (23, 19),
               (-23, 19), (23, -24), (-23, -24), (38, 3), (-38, 3),
               (0, 32), (0, -32), (45, 25), (-45, 25)]
    for (fld, freq), ids in sorted(grouped.items(), key=lambda item: (-item[0][1], item[0][0])):
        text = ax.annotate('/'.join(ids), (fld, freq), xytext=(8, 6),
                           textcoords='offset points', fontsize=9)
        chosen = None
        for dx, dy in offsets:
            text.set_position((dx, dy))
            text.set_ha('left' if dx > 0 else 'right' if dx < 0 else 'center')
            text.set_va('bottom' if dy >= 0 else 'top')
            box = text.get_window_extent(renderer).expanded(1.08, 1.1)
            inside = ax.bbox.contains(box.x0, box.y0) and ax.bbox.contains(box.x1, box.y1)
            if inside and not any(box.overlaps(other) for other in placed + point_boxes):
                chosen = (dx, dy); placed.append(box); break
        if chosen is None:
            raise ValueError(f'Cannot place scatter label without overlap: {ids}')
        if abs(chosen[0]) + abs(chosen[1]) > 25:
            ax.annotate('', (fld, freq), xytext=chosen, textcoords='offset points',
                        arrowprops={'arrowstyle': '-', 'color': '#A7B1BD', 'lw': .6}, zorder=1)
    save(fig, 'fld_freq', '05_diversity_frequency', title, 'Совпадающие точки подписаны совместно. График показывает описательное соотношение; причинный вывод не делается.')

    # FLD/FREQ 6: mean normalized density.
    title = 'Средняя частота средств апелляции к вине на 100 слов'
    fig, ax = base(title)
    values = [groups[g]['FREQ_100']['mean'] for g in GROUPS]
    labels(ax, ax.bar(range(4), values, color=[GC[g] for g in GROUPS], width=.6), 2)
    ax.set(xticks=range(4), xticklabels=GROUPS, ylim=(0, 25), yticks=range(0, 26, 5), ylabel='Реализаций на 100 слов A1–A6', xlabel='Группа диалогов')
    save(fig, 'fld_freq', '06_frequency_per_100_words', title, 'Среднее индивидуальных отношений 100 × FREQ / число слов; не отношение сумм и не общая информационная насыщенность.')

    for book in books.values():
        book.close()
    write_json(out / 'manifest.json', {'source': '06_results/summary.json',
                'source_sha256': sha256(ROOT / '06_results/summary.json'), 'figures': manifest})
    lines = ['# Диаграммы исследования', '',
             'Все графики построены из [единого расчёта](../summary.json). '
             'LLM обозначен синим цветом, человек — оранжевым; для групп и языковых уровней используется отдельная легенда.', '']
    for kind, label in [('nat', 'NAT'), ('guilt', 'GUILT'), ('fld_freq', 'FLD и FREQ')]:
        lines.extend([f'## {label}', '', f'[Все диаграммы раздела в PDF]({kind}/all_figures.pdf)', ''])
        for item in manifest:
            if item['collection'] != kind:
                continue
            png = item['png'].removeprefix('06_results/figures/')
            svg = item['svg'].removeprefix('06_results/figures/')
            lines.extend([f'### {item["title"]}', '', f'![{item["title"]}]({png})', '',
                          f'{item["caption"]} [SVG]({svg}).', ''])
    (out / 'README.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    print(f'Диаграммы: {len(manifest)}; PNG + SVG; три PDF-сборника.')


if __name__ == '__main__':
    build()
