"""Student A: queue timing, angle wrapping, direction and invalid-input checks."""
import math
import numpy as np
import pytest
from .skills import MotionSkills

def pose(deg):
    a=math.radians(deg)/2
    return np.array([0,0,.3,math.cos(a),0,0,math.sin(a)])

def test_timed_queue_and_stop():
    s=MotionSkills(lambda _:None); s.move(.5,0,0,1); s.turn(90)
    assert s.update(10,pose(0))[0]==.5
    assert s.update(10.99,pose(0))[0]==.5
    assert not s.update(11,pose(0)).any()
    assert s.update(11.02,pose(0))[2]>0
    s.stop(); assert not s.busy
    assert not s.update(12,pose(0)).any()

def test_wrap_direction_and_full_turn():
    s=MotionSkills(lambda _:None); s.turn(360)
    assert s.update(0,pose(170))[2]>0
    for i,d in enumerate([179,-170,-90,0,90,169]): s.update((i+1)*.1,pose(d))
    assert s.results[-1]['status']=='SUCCESS'
    assert abs(s.results[-1]['final_error_deg']-1)<1e-6

@pytest.mark.parametrize('value',[float('nan'),float('inf'),721])
def test_invalid_turn(value):
    with pytest.raises(ValueError): MotionSkills().turn(value)

def test_invalid_move_and_timeout():
    s=MotionSkills(lambda _:None)
    with pytest.raises(ValueError): s.move(2,0,0,1)
    with pytest.raises(ValueError): s.move(0,0,0,-1)
    s.turn(90); s.move(.5,0,0,1)
    s.update(0,pose(0)); s.update(16,pose(0))
    assert not s.busy and s.results[-1]['status'].startswith('FAIL')
