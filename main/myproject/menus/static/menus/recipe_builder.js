/* [US-03][UC-03] Progressive row controls; Django owns validation/saving. */
(() => {
  const rows = document.querySelector('#recipe-rows');
  const add = document.querySelector('#add-row');
  const total = document.querySelector('#id_items-TOTAL_FORMS');
  const template = document.querySelector('#empty-row');
  if (!rows || !add || !total || !template) return;

  function connect(row) {
    const remove = row.querySelector('.remove-row');
    const deletion = row.querySelector('input[name$="-DELETE"]');
    remove.hidden = false;
    if (deletion.checked) row.hidden = true;
    remove.addEventListener('click', () => {
      deletion.checked = true;
      row.querySelectorAll('[required]').forEach(input => { input.required = false; });
      row.hidden = true;
    });
  }

  rows.querySelectorAll('.recipe-row').forEach(connect);
  add.hidden = false;
  add.addEventListener('click', () => {
    const fragment = template.content.cloneNode(true);
    const wrapper = document.createElement('div');
    wrapper.append(fragment);
    wrapper.innerHTML = wrapper.innerHTML.replaceAll('__prefix__', total.value);
    const row = wrapper.firstElementChild;
    rows.append(row);
    total.value = String(Number(total.value) + 1);
    connect(row);
    row.querySelector('select').focus();
  });
})();
