let rosServer;
let cmdVelTopic;
let twist;

$(document).ready(function() {
    let status = $('<span>').css('color', '#FFA500').text('Pending...');
    $('#info-ros-bridge-server-status').append(status);

    if (!ros_bridge_server_ip) {
        $('#info-ros-bridge-server-status').children().last().remove();
        status = $('<span>').css('color', '#C86B57').text('Disconnected ⦿');
        $('#info-ros-bridge-server-status').append(status);
        console.warn("No ROS Bridge Server IP address provided.");
        return;
    }

    rosServer = new ROSLIB.Ros({
        url: "ws://" + ros_bridge_server_ip + ":9090"
    });

    rosServer.on('connection', function() {
        $('#up,#down,#center,#left,#right').prop('disabled', false);

        $('#info-ros-bridge-server-status').children().last().remove();
        status = $('<span>').css('color', '#779A68').text('Connected ⦿');
        $('#info-ros-bridge-server-status').append(status);
    });
    rosServer.on('error', function(error) {
        $('#info-ros-bridge-server-status').children().last().remove();
        status = $('<span>').css('color', '#C86B57').text('Disconnected ⦿');
        $('#info-ros-bridge-server-status').append(status);
    });

    cmdVelTopic = new ROSLIB.Topic({
        ros : rosServer,
        name : '/cmd_vel',
        messageType : 'geometry_msgs/Twist'
    });

    twist = new ROSLIB.Message({
        linear : {
            x : 0.0,
            y : 0.0,
            z : 0.0
        },
        angular : {
            x : 0.0,
            y : 0.0,
            z : 0.0
        }
    });
});

$(document).ready(function() {
    let status = $('<span>').css('color', '#FFA500').text('Pending...');
    $('#info-streaming-server-status').append(status);

    $.ajax({
        url: "http://" + streaming_server_ip + "/bot_stream",
        type: 'GET',
        success: function() {
            let video_frame = $('#streaming-video');
            
            video_frame.removeAttr('srcdoc');
            video_frame.attr('src', "http://" + streaming_server_ip + "/bot_stream");
            $('#edit, #default').prop("disabled", false);
    
            $('#bitrate').val('4000');
            $('#speed-preset').val('ultrafast');
            $('#resolution').val('1920x1080');
            $('.parameter-field').prop('disabled', true);

            $('#info-streaming-server-status').children().last().remove();
            status = $('<span>').css('color', '#779A68').text('Connected ⦿');
            $('#info-streaming-server-status').append(status);
        },
        error: function() {
            $('#info-streaming-server-status').children().last().remove();
            status = $('<span>').css('color', '#C86B57').text('Disconnected ⦿');
            $('#info-streaming-server-status').append(status);
        }
    });
});

let last_valid_bitrate;
let last_valid_speed_preset;
let last_valid_resolution;
$('#edit').click(function() {
    last_valid_bitrate = $('#bitrate').val();
    last_valid_speed_preset = $('#speed-preset').val();
    last_valid_resolution = $('#resolution').val();
    $('.parameter-field, #update').prop('disabled', false);
});

$('#default').click(function() {
    $('#bitrate').val('4000');
    $('#speed-preset').val('ultrafast');
    $('#resolution').val('1920x1080');
    $('.parameter-field, #update').prop('disabled', true);

    $.post(post_request_route, {bitrate: "4000",
        speed_preset: "ultrafast",
        resolution: "1920x1080"}, function() {
        alert("Data sent to streaming server!");
    });
});


$('#update').click(function() {
    let bitrate = $('#bitrate').val();
    let speed_preset = $('#speed-preset').val();
    let resolution = $('#resolution').val();

    // Check if bitrate is an integer
    if (!Number.isInteger(Number(bitrate))) {
        alert("Please enter a whole number for the bitrate.");
        $('#bitrate').val(last_valid_bitrate);  // Restore the last valid value
        return;
    }

    // Check if resolution is in the format intxint
    var resolution_parts = resolution.split('x');
    if (resolution_parts.length != 2 || !Number.isInteger(Number(resolution_parts[0])) || !Number.isInteger(Number(resolution_parts[1]))) {
        alert("Please enter the resolution in the format 'Width x Height' (e.g., 1920x1080), where both Width and Height are whole numbers.");
        $('#resolution').val(last_valid_resolution);  // Restore the last valid value
        return;
    }

    // Check if speed_preset is in the list
    var valid_presets = ['None', 'ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow', 'placebo'];
    if (!valid_presets.includes(speed_preset)) {
        alert("Please select a speed preset from the following options: " + valid_presets.join(', '));
        $('#speed-preset').val(last_valid_speed_preset);  // Restore the last valid value
        return;
    }

    // If all checks pass, update the last valid values
    last_valid_bitrate = bitrate;
    last_valid_speed_preset = speed_preset;
    last_valid_resolution = resolution;
    
    $('.parameter-field, #update').prop('disabled', true);

    $.post(post_request_route, {bitrate: bitrate, speed_preset: speed_preset, resolution: resolution}, function() {
        alert("Data sent to streaming server!");
    });
});



function keydownAction(key, elementId) {
    $(document).keydown(function(event) {
        if (event.key.toLowerCase() == key) {
            var button = $('#' + elementId);
            if (!button.prop('disabled')) {
                button.click();
                button.addClass('active');
                setTimeout(function() {
                    button.removeClass('active');
                }, 150);
            }
        }
    });
};


let actions = {
    'w': { buttonId: 'up', actionFunction: move_forward },
    'a': { buttonId: 'left', actionFunction: turn_left },
    's': { buttonId: 'center', actionFunction: stop_movement },
    'x': { buttonId: 'down', actionFunction: move_backward },
    'd': { buttonId: 'right', actionFunction: turn_right }
};

$.each(actions, function(key, value) {
    keydownAction(key, value.buttonId);
    $('#' + value.buttonId).click(value.actionFunction);
});


const time_step = 100;

const BURGER_MAX_LIN_VEL = 0.22;
const BURGER_MAX_ANG_VEL = 2.84;

const LIN_VEL_STEP_SIZE = 0.01;
const ANG_VEL_STEP_SIZE = 0.1;


let movement_timer = null;

let current_linear_velocity = 0;
let current_angular_velocity = 0;
let target_linear_velocity = 0;
let target_angular_velocity = 0;

function makeSimpleProfile(current, target, slop) {
    // increase current by slop, not more than target
    if (target > current) current = Math.min(target, current + slop);
    // descrease current by slop, not less than target
    else if (target < current) current = Math.max(target, current - slop);
    else current = target

    return current
}

function constrain(input, low, high) {
	if (input < low) input = low;
	else if (input > high) input = high;
	else input = input;
	return input;
}

function checkLimitVelocity(type, velocity) {
	if (type == 'linear') return constrain(velocity, -BURGER_MAX_LIN_VEL, BURGER_MAX_LIN_VEL);
	else return constrain(velocity, -BURGER_MAX_ANG_VEL, BURGER_MAX_ANG_VEL);
}


function initiate_movement(movement) {
    current_linear_velocity = makeSimpleProfile(current_linear_velocity, target_linear_velocity, LIN_VEL_STEP_SIZE);
    current_angular_velocity = makeSimpleProfile(current_angular_velocity, target_angular_velocity, ANG_VEL_STEP_SIZE);

    if (movement_timer) clearInterval(movement_timer);

    movement_timer = setInterval(function() {
        twist.linear.x = current_linear_velocity;
        twist.angular.z = current_angular_velocity;
        cmdVelTopic.publish(twist);
        console.log(`Movement: ${movement}, Linear Vel: ${current_linear_velocity}, Angular Vel: ${current_angular_velocity}`);
    }, time_step);
}

function move_forward() {
	target_linear_velocity = checkLimitVelocity('linear', target_linear_velocity + LIN_VEL_STEP_SIZE);

    initiate_movement('forward');
}

function move_backward() {
	target_linear_velocity = checkLimitVelocity('linear', target_linear_velocity - LIN_VEL_STEP_SIZE);

    initiate_movement('backward');
}

function turn_right() {
	target_angular_velocity = checkLimitVelocity('angular', target_angular_velocity - ANG_VEL_STEP_SIZE);

    initiate_movement('right');
}

function turn_left() {
	target_angular_velocity = checkLimitVelocity('angular', target_angular_velocity + ANG_VEL_STEP_SIZE);

    initiate_movement('left');
}

function stop_movement() {
	current_linear_velocity = 0;
	current_angular_velocity = 0;
	target_linear_velocity = 0;
	target_angular_velocity = 0;

    initiate_movement('stop');
}