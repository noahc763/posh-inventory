(function(){
  const resultEl = document.getElementById('result');
  function onDetected(res){
    const code = res && res.codeResult && res.codeResult.code;
    if(!code) return;
    resultEl.textContent = 'Detected: ' + code;
    // Auto-submit via POST using a hidden form
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/scan';
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'barcode';
    input.value = code;
    form.appendChild(input);
    document.body.appendChild(form);
    Quagga.stop();
    form.submit();
  }

  if(!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia){
    resultEl.textContent = 'Camera not supported in this browser.';
    return;
  }

  Quagga.init({
    inputStream: {
      type: 'LiveStream',
      target: document.querySelector('#interactive'),
      constraints: { facingMode: 'environment' }
    },
    decoder: { readers: ['ean_reader','ean_8_reader','upc_reader','upc_e_reader','code_128_reader'] }
  }, function(err){
    if(err){ resultEl.textContent = err; return; }
    Quagga.start();
  });

  Quagga.onDetected(onDetected);
})();
