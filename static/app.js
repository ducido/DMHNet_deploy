// Get the canvas and context
var canvas = document.getElementById('myCanvas');
var context = canvas.getContext('2d');

var image = new Image();
image.src = imageUrl;
// console.log("imageUrl" + imageUrl);
image.onload = function() {
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
};

// Draw a circle at the given coordinates
function drawPoint(x, y) {
    context.beginPath();
    context.arc(x, y, 5, 0, 2 * Math.PI, false);
    context.fillStyle = 'red';
    context.fill();
}

var isListening = false;
var canvasClickListener;

var toggleButton = document.getElementById('toggleButton');
var count = 0
toggleButton.addEventListener('click', function() {
    if (isListening) {
        // If we're currently listening for clicks, remove the event listener and update the button text
        canvas.removeEventListener('click', canvasClickListener);
        toggleButton.textContent = 'Start';
    } else {
        // If we're not currently listening for clicks, add the event listener and update the button text
        canvasClickListener = function(event) {
            var rect = canvas.getBoundingClientRect();
            var x = event.clientX - rect.left;
            var y = event.clientY - rect.top;
            count = count + 1;
            drawPoint(x, y);
            console.log("x: " + x + " y: " + y + " count: " + count);
            // Send a request to the server to save the coordinates
            fetch('/save_point', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({coordinates: [x, y]}),
            });
        };
        canvas.addEventListener('click', canvasClickListener);
        toggleButton.textContent = 'Stop';
    }
    // Toggle the isListening flag
    if(count < 8) isListening = !isListening;
    else {
        console.log('Finish labeling corners');
        // fetch('/run_model', {
        //     method: 'GET',
        //     headers: {
        //         'Content-Type': 'application/json',
        //     },
        //     body: JSON.stringify({})
        // }
        // );
        // return;
    }
    return;
});
document.getElementById('runModel').addEventListener('click', function() {
    fetch('/run_model')
    .then(response => response.text())
    .then(result => console.log(result))
    .catch(error => console.error('Error:', error));
});

// // Add an event listener for clicks on the canvas
// canvas.addEventListener('click', function(event) {
//     var rect = canvas.getBoundingClientRect();
//     var x = event.clientX - rect.left;
//     var y = event.clientY - rect.top;

//     drawPoint(x, y);
//     console.log("x: " + x + " y: " + y);
//     // Send a request to the server to save the coordinates
//     fetch('/save_point', {
//     method: 'POST',
//     headers: {
//         'Content-Type': 'application/json',
//     },
//     body: JSON.stringify({coordinates: [x, y]}),
// });
// });

// // Get the saved coordinates and draw them
// $.getJSON('/save_point', function(data) {
//     for (var i = 0; i < data.length; i++) {
//         drawPoint(data[i][0], data[i][1]);
//     }
// });