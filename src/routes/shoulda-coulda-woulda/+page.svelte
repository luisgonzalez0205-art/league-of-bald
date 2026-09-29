<script>
	// Shoulda Coulda Woulda: each team's record if it had played another team's schedule.
	// Data is rebuilt weekly by the "Update Sleeper standings" GitHub Action.
	import { onMount } from 'svelte';

	const SOURCE =
		'https://raw.githubusercontent.com/luisgonzalez0205-art/league-of-bald/master/static/shoulda-coulda-woulda.json';

	let data = null;
	let error = null;

	const rec = (r) => `${r.w}-${r.l}${r.t ? `-${r.t}` : ''}`;
	const signed = (n) => (n > 0 ? `+${n.toFixed(2)}` : n.toFixed(2));

	onMount(async () => {
		try {
			const res = await fetch(SOURCE, { cache: 'no-store' });
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			data = await res.json();
		} catch (e) {
			error = e.message;
		}
	});

	$: teamById = data ? Object.fromEntries(data.teams.map((t) => [t.roster_id, t])) : {};
	$: games = data?.weeks?.length || 0;
	// Shade each cell from red (few wins) to green (many wins)
	const shade = (w, n) => {
		if (!n) return 'transparent';
		const pct = w / n;
		const color = pct >= 0.5 ? '46, 160, 67' : '218, 54, 51';
		const strength = Math.abs(pct - 0.5) * 2 * 0.45;
		return `rgba(${color}, ${strength.toFixed(2)})`;
	};
</script>

<svelte:head>
	<title>Shoulda Coulda Woulda</title>
</svelte:head>

<div class="page">
	<h1>Shoulda Coulda Woulda</h1>

	{#if error}
		<p class="note">This page couldn't load ({error}). Run the "Update Sleeper standings" workflow on GitHub to create it.</p>
	{:else if !data}
		<p class="note">Loading…</p>
	{:else}
		<p class="note">
			What each team's record would be with every other team's schedule, through week
			{data.weeks[data.weeks.length - 1]}. Luck is actual wins minus the average across all
			schedules.
		</p>

		<h2>Luck and schedule</h2>
		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						<th class="left">Team</th>
						<th>Actual</th>
						<th>Expected wins</th>
						<th>Luck</th>
						<th title="1 = opponents scored the most against them">Schedule rank</th>
						<th class="left">Best schedule</th>
						<th class="left">Worst schedule</th>
					</tr>
				</thead>
				<tbody>
					{#each data.summary as s (s.roster_id)}
						<tr>
							<td class="left">
								<div class="team">
									{#if s.avatar}<img src={s.avatar} alt="" width="28" height="28" loading="lazy" />{/if}
									<span class="team-name">{s.team}</span>
								</div>
							</td>
							<td>{rec(s.actual)}</td>
							<td>{s.expected_wins.toFixed(2)}</td>
							<td class:good={s.luck > 0} class:bad={s.luck < 0}>{signed(s.luck)}</td>
							<td>{s.sos_rank}</td>
							<td class="left">{s.best_schedule.team} ({rec(s.best_schedule)})</td>
							<td class="left">{s.worst_schedule.team} ({rec(s.worst_schedule)})</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<p class="hint">Schedule rank 1 is the toughest schedule: that team's opponents scored the most against them.</p>

		<h2>Every schedule</h2>
		<p class="hint">Each row is a team; each column is whose schedule they're playing. The outlined cell is their real record.</p>
		<div class="table-wrap">
			<table class="matrix">
				<thead>
					<tr>
						<th class="left sticky">Team</th>
						{#each data.teams as t (t.roster_id)}
							<th class="col-head" title={`${t.team}'s schedule`}>
								{#if t.avatar}
									<img src={t.avatar} alt={t.team} width="26" height="26" loading="lazy" />
								{:else}
									{t.team.slice(0, 3)}
								{/if}
							</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each data.matrix as row (row.roster_id)}
						<tr>
							<td class="left sticky team-name">{teamById[row.roster_id]?.team}</td>
							{#each row.cells as c (c.schedule_of)}
								<td
									class:own={c.schedule_of === row.roster_id}
									style="background: {shade(c.w + 0.5 * c.t, games)}"
									title={`${teamById[row.roster_id]?.team} with ${teamById[c.schedule_of]?.team}'s schedule`}
								>
									{rec(c)}
								</td>
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<p class="updated">Updated {data.updated}</p>
	{/if}
</div>

<style>
	.page {
		max-width: 1100px;
		margin: 0 auto;
		padding: 1.5rem 1rem 3rem;
	}
	h1,
	h2 {
		text-align: center;
	}
	h2 {
		margin-top: 2.25rem;
		margin-bottom: 0.5rem;
	}
	.note {
		text-align: center;
		max-width: 62ch;
		margin: 0 auto 1rem;
		opacity: 0.8;
	}
	.hint,
	.updated {
		text-align: center;
		font-size: 0.8rem;
		opacity: 0.65;
		margin: 0.5rem auto 0.75rem;
	}
	.table-wrap {
		overflow-x: auto;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-variant-numeric: tabular-nums;
	}
	th,
	td {
		padding: 0.5rem 0.45rem;
		text-align: center;
		white-space: nowrap;
		border-bottom: 1px solid color-mix(in srgb, currentColor 15%, transparent);
	}
	th {
		font-size: 0.82rem;
		font-weight: 600;
		opacity: 0.75;
		border-bottom-width: 2px;
	}
	.left {
		text-align: left;
	}
	.team {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	img {
		border-radius: 50%;
		object-fit: cover;
		vertical-align: middle;
	}
	.team-name {
		font-weight: 600;
	}
	.good {
		color: rgb(46, 160, 67);
		font-weight: 600;
	}
	.bad {
		color: rgb(218, 54, 51);
		font-weight: 600;
	}
	.matrix td {
		font-size: 0.85rem;
	}
	.matrix td.own {
		outline: 2px solid currentColor;
		outline-offset: -3px;
		font-weight: 700;
	}
	.col-head {
		min-width: 3rem;
	}
	.sticky {
		position: sticky;
		left: 0;
		background: var(--fff, Canvas);
		z-index: 1;
	}
	@media (max-width: 600px) {
		th,
		td {
			padding: 0.4rem 0.3rem;
			font-size: 0.8rem;
		}
	}
</style>
