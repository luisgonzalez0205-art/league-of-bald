<script>
	// Weekly Performance Awards + season tallies.
	// Data is rebuilt weekly by the "Update Sleeper standings" GitHub Action.
	import { onMount } from 'svelte';

	const SOURCE =
		'https://raw.githubusercontent.com/luisgonzalez0205-art/league-of-bald/master/static/performance-awards.json';

	let data = null;
	let error = null;
	let week = null;

	onMount(async () => {
		try {
			const res = await fetch(SOURCE, { cache: 'no-store' });
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			data = await res.json();
			if (data.weeks.length) week = data.weeks[data.weeks.length - 1];
		} catch (e) {
			error = e.message;
		}
	});

	$: current = data?.weekly.find((w) => w.week === week);
	$: types = data ? Object.fromEntries(data.award_types.map((a) => [a.key, a])) : {};
	const hideBroken = (e) => (e.currentTarget.style.visibility = 'hidden');
</script>

<svelte:head>
	<title>Performance Awards</title>
</svelte:head>

<div class="page">
	<h1>Performance Awards</h1>

	{#if error}
		<p class="note">This page couldn't load ({error}). Run the "Update Sleeper standings" workflow on GitHub to create it.</p>
	{:else if !data}
		<p class="note">Loading…</p>
	{:else if !data.weeks.length}
		<p class="note">Awards start after week 1 is final.</p>
	{:else}
		<div class="week-picker">
			<label for="week">Week</label>
			<select id="week" bind:value={week}>
				{#each [...data.weeks].reverse() as w}
					<option value={w}>Week {w}</option>
				{/each}
			</select>
		</div>

		{#if current}
			{#if !current.projections_available}
				<p class="hint">Projections weren't available this week, so Overachiever and Below Expectation are skipped.</p>
			{/if}
			<div class="awards">
				{#each current.awards as a (a.key)}
					<article class="award">
						<header>
							<span class="emoji" aria-hidden="true">{a.emoji}</span>
							<div>
								<h3>{a.title}</h3>
								<p class="desc">{a.description}</p>
							</div>
						</header>

						{#if a.player}
							<div class="player">
								{#if a.player.image}
									<img class="player-img" src={a.player.image} alt="" width="44" height="44" loading="lazy" on:error={hideBroken} />
								{/if}
								<div>
									<div class="player-name">{a.player.name}</div>
									<div class="small">{a.player.position}{a.player.nfl_team ? ` · ${a.player.nfl_team}` : ''}</div>
								</div>
							</div>
						{/if}

						<div class="winner">
							{#if a.avatar}<img src={a.avatar} alt="" width="26" height="26" loading="lazy" />{/if}
							<span class="team-name">{a.team}</span>
							<span class="value">{a.value}</span>
						</div>
						{#if a.detail}<p class="small detail">{a.detail}</p>{/if}
					</article>
				{/each}
			</div>
		{/if}

		<h2>Season tallies</h2>
		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						<th class="left">Team</th>
						<th>Total</th>
						<th class="left">Awards won</th>
					</tr>
				</thead>
				<tbody>
					{#each data.tallies as t (t.roster_id)}
						<tr>
							<td class="left">
								<div class="team">
									{#if t.avatar}<img src={t.avatar} alt="" width="26" height="26" loading="lazy" />{/if}
									<span class="team-name">{t.team}</span>
								</div>
							</td>
							<td class="total">{t.total}</td>
							<td class="left">
								<div class="chips">
								{#each Object.entries(t.counts).sort((x, y) => y[1] - x[1]) as [key, n]}
									<span class="chip" title={types[key]?.title}>{types[key]?.emoji} {types[key]?.title.replace('The ', '')} ×{n}</span>
								{/each}
								</div>
							</td>
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
		margin-top: 2.5rem;
	}
	.note,
	.hint {
		text-align: center;
		max-width: 62ch;
		margin: 0 auto 1rem;
		opacity: 0.8;
	}
	.hint {
		font-size: 0.85rem;
	}
	.week-picker {
		display: flex;
		justify-content: center;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 1.25rem;
	}
	select {
		font: inherit;
		padding: 0.35rem 0.6rem;
		border-radius: 6px;
	}
	.awards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
		gap: 0.9rem;
	}
	.award {
		border: 1px solid color-mix(in srgb, currentColor 18%, transparent);
		border-radius: 10px;
		padding: 0.85rem;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
	.award header {
		display: flex;
		gap: 0.6rem;
		align-items: flex-start;
	}
	.emoji {
		font-size: 1.7rem;
		line-height: 1;
	}
	h3 {
		margin: 0;
		font-size: 1rem;
	}
	.desc,
	.small {
		margin: 0.1rem 0 0;
		font-size: 0.8rem;
		opacity: 0.7;
	}
	.player {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}
	.player-img {
		border-radius: 50%;
		object-fit: cover;
		background: color-mix(in srgb, currentColor 8%, transparent);
	}
	.player-name {
		font-weight: 600;
	}
	.winner {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: auto;
	}
	.winner img,
	.team img {
		border-radius: 50%;
		object-fit: cover;
	}
	.team-name {
		font-weight: 600;
	}
	.value {
		margin-left: auto;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.detail {
		margin: 0;
	}
	.table-wrap {
		overflow-x: auto;
	}
	table {
		width: 100%;
		border-collapse: collapse;
	}
	th,
	td {
		padding: 0.55rem 0.45rem;
		text-align: center;
		border-bottom: 1px solid color-mix(in srgb, currentColor 15%, transparent);
		vertical-align: middle;
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
		white-space: nowrap;
	}
	.total {
		font-weight: 700;
		font-size: 1.05rem;
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
	}
	.chip {
		font-size: 0.78rem;
		padding: 0.15rem 0.5rem;
		border-radius: 999px;
		background: color-mix(in srgb, currentColor 9%, transparent);
		white-space: nowrap;
	}
	.updated {
		text-align: center;
		font-size: 0.8rem;
		opacity: 0.6;
		margin-top: 1rem;
	}
</style>
