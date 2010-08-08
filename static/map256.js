var map;
var users = new Object();
var marker_position = 0;
var markers_visible = false;
var gradient_visible = false;
var random_colors = new Array();
random_colors[0] = '#556270';
random_colors[1] = '#4ECDC4';
random_colors[2] = '#C7F464';
random_colors[4] = '#FF6B6B';
random_colors[5] = '#C44D58';

function hex (c) {
	var s = "0123456789abcdef";
	var i = parseInt (c);
	if (i == 0 || isNaN (c))
		return "00";
	i = Math.round (Math.min (Math.max (0, i), 255));
	return s.charAt ((i - i % 16) / 16) + s.charAt (i % 16);
}

function convertToHex (rgb) {
	return hex(rgb[0]) + hex(rgb[1]) + hex(rgb[2]);
}

function trim (s) { 
	return (s.charAt(0) == '#') ? s.substring(1, 7) : s 
}

function convertToRGB (hex) {
	var color = [];
	color[0] = parseInt ((trim(hex)).substring (0, 2), 16);
	color[1] = parseInt ((trim(hex)).substring (2, 4), 16);
	color[2] = parseInt ((trim(hex)).substring (4, 6), 16);
	return color;
}

function getUrlVars(url) {
    var vars = [], hash;
    var hashes = url.slice(window.location.href.indexOf('?') + 1).split('&');
    for(var i = 0; i < hashes.length; i++)
    {
        hash = hashes[i].split('=');
        vars.push(hash[0]);
        vars[hash[0]] = hash[1];
    }
    return vars;
}

function isArray(a) {
    return Object.prototype.toString.apply(a) === '[object Array]';
}

$.extend({URLEncode:function(c){var o='';var x=0;c=c.toString();var r=/(^[a-zA-Z0-9_.]*)/;
  while(x<c.length){var m=r.exec(c.substr(x));
    if(m!=null && m.length>1 && m[1]!=''){o+=m[1];x+=m[1].length;
    }else{if(c[x]==' ')o+='+';else{var d=c.charCodeAt(x);var h=d.toString(16);
    o+='%'+(h.length<2?'0':'')+h.toUpperCase();}x++;}}return o;},
URLDecode:function(s){var o=s;var binVal,t;var r=/(%[^%]{2})/;
  while((m=r.exec(o))!=null && m.length>1 && m[1]!=''){b=parseInt(m[1].substr(1),16);
  t=String.fromCharCode(b);o=o.replace(m[1],t);}return o;}
});

function toggle_gradient() {
	var start_col = convertToRGB('#FF0000');
	var end_col = convertToRGB('#0000FF');
	var alpha = 0.5;
	var cur_col = '#FF0000';

	if ( gradient_visible == false ) {
		for (var x = 0; x < users['huh']['lines'].length; x++) {
			var c = [];
			var tmp_a = 1 - (x / (users['huh']['lines'].length - 1));
			c[0] = start_col[0] * tmp_a + (1 - tmp_a) * end_col[0];
			c[1] = start_col[1] * tmp_a + (1 - tmp_a) * end_col[1];
			c[2] = start_col[2] * tmp_a + (1 - tmp_a) * end_col[2];
			cur_col = '#' + convertToHex(c);
			users['huh']['lines'][x].setOptions({ strokeColor: cur_col});
		}

		gradient_visible = true;
	} else {
		for (var x = 0; x < users['huh']['lines'].length; x++) {
			users['huh']['lines'][x].setOptions({ strokeColor: '#000000'});
		}

		gradient_visible = false;
	}
}

function toggle_markers() {
	if ( markers_visible == false ) {
		for (var x in users['huh']['markers']) {
			users['huh']['markers'][x].setVisible(true);
		}
		markers_visible = true;
	} else {
		for (var x in users['huh']['markers']) {
			users['huh']['markers'][x].setVisible(false);
		}
		markers_visible = false;
	}
}

function goto_previous() {
	users['huh']['markers'][marker_position].setVisible(false);

	if (marker_position < (users['huh']['markers'].length-2) ) {
		marker_position = marker_position + 1;
	} else {
		marker_position = users['huh']['markers'].length - 1;
	}

	users['huh']['markers'][marker_position].setVisible(true);
}

function goto_next() {
	users['huh']['markers'][marker_position].setVisible(false);

	if (marker_position == 0) {
		marker_position = 0;
	} else {
		marker_position = marker_position - 1;
	}

	users['huh']['markers'][marker_position].setVisible(true);
}

function setvalue(event, ui) {
	var valx = $("#slider").slider( "option", "value" );
	users['huh']['markers'][marker_position].setVisible(false);
	marker_position = (users['huh']['markers'].length-1) - valx;
	users['huh']['markers'][marker_position].setVisible(true);
	map.setCenter(users['huh']['markers'][marker_position].getPosition());
}

function goto_earliest() {
	users['huh']['markers'][marker_position].setVisible(false);
	marker_position = users['huh']['markers'].length - 1;
	users['huh']['markers'][marker_position].setVisible(true);
}

function goto_latest() {
	users['huh']['markers'][marker_position].setVisible(false);
	marker_position = 0;
	users['huh']['markers'][marker_position].setVisible(true);
}

function createMarker(marker, infowindow) {
	google.maps.event.addListener(marker, 'click', function() {
		infowindow.open(map, marker);
	});
}

function add_user_to_map(user_key, point_data, line_color) {
    if (point_data.length < 1) {
        return;
    }

    users[user_key] = new Object();
    var lines = new Array();

	for (var i=1; i<point_data.length; i++) {
		if (point_data[i-1]['location'] != point_data[i]['location']) {
			var tmp_a = point_data[i-1]['location'].split(",");
			var tmp_b = point_data[i]['location'].split(",");

			lines.push(new google.maps.Polyline({
				path: new Array(new google.maps.LatLng(tmp_a[0], tmp_a[1]), new google.maps.LatLng(tmp_b[0], tmp_b[1])),
				strokeColor: line_color,
				strokeOpacity: 1.0,
				strokeWeight: 3,
				map: map
			}));
		}
	}

    users[user_key]['lines'] = lines;
}

function add_markers_to_user(user_key, marker_data) {
    var markers = new Array();

    for (var key in marker_data) {
        point = marker_data[key]['location'].split(',');
        markers.push(new google.maps.Marker({
		    position: new google.maps.LatLng(point[0], point[1]),
		    map: map,
		    title: marker_data[key]['title'],
		    visible: false
	    }));
    }

    users[user_key]['markers'] = markers;
}

function add_infowindows_to_user(user_key, infowindow_data) {
    var infowindows = new Array();

    for (var key in infowindow_data) {
        infowindows.push(new google.maps.InfoWindow({
	        content: infowindow_data[key]['content'],
		    maxWidth: 200
	    }));
    }

	users[user_key]['infowindows'] = infowindows;
}

function add_front_page_data(retrieved_data) {
    for (var key in retrieved_data) {
        user = retrieved_data[key];
        var info = new Object();
        info['account_key'] = user['account_key'];
        info['url'] = user['url'];
        info['name'] = user['name'];
        info['color'] = random_colors[key % random_colors.length];
        $.getJSON('/data/'+user['account_key'], info, function(data) {
            if (isArray(data)) {
                if (data.length < 1) {
                    return;
                }
            }

            local = getUrlVars(this.data);
            add_user_to_map(local['account_key'], data, $.URLDecode(local['color']));
            marker_data = new Array();
            marker_dict = new Object();
            marker_dict['location'] = data[0]['location'];
            marker_dict['title'] = local['name'];
            marker_data[0] = marker_dict;
            add_markers_to_user(local['account_key'], marker_data);
            infowindow_data = new Array();
            infowindow_dict = new Object();
            infowindow_dict['content'] = '<h4><a href=\"'+$.URLDecode(local['url'])+'\">'+local['name']+'</a></h4>';
            infowindow_data[0] = infowindow_dict;
            add_infowindows_to_user(local['account_key'], infowindow_data);
            createMarker(users[local['account_key']]['markers'][0], users[local['account_key']]['infowindows'][0]);
            users[local['account_key']]['markers'][0].setVisible(true);
        });
    }
}

function add_user_page_data(retrieved_data) {
    add_user_to_map('huh', retrieved_data, '#000000');
    marker_data = new Array();
    infowindow_data = new Array();
    for (var key in retrieved_data) {
        var marker_dict = new Object();
        marker_dict['location'] = retrieved_data[key]['location'];
        marker_dict['title'] = 'foo';
        var infowindow_dict = new Object();
        infowindow_dict['content'] = "<p><strong>"+retrieved_data[key]['description']+"</strong><br><em>"+retrieved_data[key]['occurred']+"</em></p>",
        marker_data[key] = marker_dict;
        infowindow_data[key] = infowindow_dict;
    }
    add_markers_to_user('huh', marker_data);
    add_infowindows_to_user('huh', infowindow_data);

    for (var key in marker_data) {
        createMarker(users['huh']['markers'][key], users['huh']['infowindows'][key]);
    }

    users['huh']['markers'][0].setVisible(true);

    var tmp = retrieved_data[0]['location'].split(",");
	centerpt = new google.maps.LatLng(tmp[0], tmp[1]);
	map.setCenter(centerpt);

	var sld_max = retrieved_data.length-1
	$(document).ready(function() {
	  $("#slider").slider({ min: 0, max: sld_max, slide: setvalue, value: sld_max });
	});

	google.maps.event.addDomListener(document.getElementById("g_n"), "click", function(ev) {
		map.setCenter(users['huh']['markers'][marker_position].getPosition());
		$("#slider").slider( "option", "value", sld_max - marker_position );
	});

	google.maps.event.addDomListener(document.getElementById("g_l"), "click", function(ev) {
		map.setCenter(users['huh']['markers'][marker_position].getPosition());
		$("#slider").slider( "option", "value", sld_max - marker_position );
	});

	google.maps.event.addDomListener(document.getElementById("g_p"), "click", function(ev) {
		map.setCenter(users['huh']['markers'][marker_position].getPosition());
		$("#slider").slider( "option", "value", sld_max - marker_position );
	});

	google.maps.event.addDomListener(document.getElementById("g_e"), "click", function(ev) {
		map.setCenter(users['huh']['markers'][marker_position].getPosition());
		$("#slider").slider( "option", "value", sld_max - marker_position );
	});
}

function look_up_user(retrieved_data) {
    $.getJSON('/data/'+retrieved_data['account_key'], function(data) { add_user_page_data(data); });
}

function change_page_type (target_type) {
    //FIXME: clear page (remove all users, anything else?)

    switch (target_type)
    {
        case 'frontpage':
            $.getJSON('/front_page_data', function(data) { add_front_page_data(data); })
            break;
        case 'userpage':
            var pathArray = window.location.pathname.split( '/' );
            $.getJSON('/kl/'+pathArray[2], function(data) { look_up_user(data); })
            break;
        default:
            $.getJSON('/front_page_data', function(data) { add_front_page_data(data); })
            break;
    }
}

function initialize_page () {
    //FIXME: Need to redo this with a proper bounding box at some point
    var mapOptions = {
        zoom: 4,
        center: new google.maps.LatLng(37.958135,-91.773429),
        mapTypeId: google.maps.MapTypeId.ROADMAP
    };

    map = new google.maps.Map(document.getElementById("map_canvas"), mapOptions);

    var pathArray = window.location.pathname.split( '/' );
    //FIXME: Not at all pretty at the moment
    if ( pathArray.length == 2 ) {
        change_page_type('frontpage');
    } else {
        change_page_type('userpage');
    }
}

$(document).ajaxStart(function(){
    $('#ajaxBusy').show();
}).ajaxStop(function(){
    $('#ajaxBusy').hide();
});