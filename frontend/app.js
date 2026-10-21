const search = document.querySelector('#symptom-search');
const suggestions = document.querySelector('#suggestions');
const chosenBox = document.querySelector('#chosen-symptoms');
const assessButton = document.querySelector('#assess-button');
const result = document.querySelector('#result');
const clearButton = document.querySelector('#clear-symptoms');
let selected = [];
let timer;

document.querySelectorAll('[data-scroll]').forEach(button => button.addEventListener('click', () => document.getElementById(button.dataset.scroll).scrollIntoView({ behavior: 'smooth' })));

function renderChosen() {
  chosenBox.innerHTML = '';
  if (!selected.length) chosenBox.innerHTML = '<span class="empty-selection">No symptoms selected yet</span>';
  selected.forEach(item => { const chip = document.createElement('button'); chip.className = 'chip'; chip.textContent = `${item.label} ×`; chip.title = 'Remove symptom'; chip.onclick = () => { selected = selected.filter(value => value.id !== item.id); renderChosen(); }; chosenBox.append(chip); });
  assessButton.disabled = selected.length === 0;
  clearButton.hidden = selected.length === 0;
}

clearButton.addEventListener('click', () => { selected = []; suggestions.innerHTML = ''; result.innerHTML = ''; renderChosen(); search.focus(); });

function showError(message) { result.innerHTML = `<p class="error">${message}</p>`; }

search.addEventListener('input', () => {
  clearTimeout(timer); suggestions.innerHTML = '';
  const query = search.value.trim(); if (query.length < 2) return;
  timer = setTimeout(async () => {
    try {
      const response = await fetch(`/api/symptom-checker/symptoms?q=${encodeURIComponent(query)}`);
      const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Could not search symptoms.');
      data.symptoms.filter(item => !selected.some(value => value.id === item.id)).forEach(item => {
        const button = document.createElement('button'); button.className = 'suggestion'; button.type = 'button'; button.setAttribute('role', 'option'); button.textContent = item.label;
        button.onclick = () => { selected.push(item); search.value = ''; suggestions.innerHTML = ''; renderChosen(); search.focus(); };
        suggestions.append(button);
      });
    } catch (error) { showError(error.message); }
  }, 300);
});

assessButton.addEventListener('click', async () => {
  assessButton.disabled = true; assessButton.textContent = 'Finding guidance…'; result.innerHTML = '';
  try {
    const response = await fetch('/api/symptom-checker/assess', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symptoms: selected.map(item => item.id) }) });
    const data = await response.json(); if (!response.ok) throw new Error(data.error || 'We could not complete that check.');
    const matches = data.possible_matches.map(item => `<li><strong>${item.specialist}</strong> — possible match: ${item.condition}</li>`).join('');
    result.innerHTML = `<div class="result-card"><p class="eyebrow">SUGGESTED NEXT STEP</p><h3>Speak with a ${data.recommendation}</h3><p>These are possible matches from the selected symptoms:</p><ul>${matches}</ul><p class="fine-print">${data.disclaimer}</p></div>`;
  } catch (error) { showError(error.message); } finally { assessButton.textContent = 'Get guidance'; renderChosen(); }
});
