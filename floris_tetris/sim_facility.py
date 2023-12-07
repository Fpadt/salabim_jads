import salabim as sim
from datetime import datetime
import pandas as pd

# ------------------------------------------------------------
# Simulation code for M/M/c queue
# ------------------------------------------------------------
# function to run simulation
def sim_facility(
    inter_arr_time_distr,  # inter-arrival time distribution
    energy_request_distr,  # energy request distribution
    number_of_EVSE,  # number of EVSE's
    sim_time,
    fixed_utilization=False,
    time_unit="minutes",
    random_seed='*',
    run=1,
):
    """
    Simulate a charging facility for electric vehicles.

    Args:
        ev_arrival_rate (float): The rate of EV arrivals per hour.
        energy_req_rate (float): The rate of energy requirement per hour.
        number_of_EVSE (int, optional): The number of EVSE's (Electric Vehicle Supply Equipment). Defaults to 1.
        sim_time (int, optional): The simulation time in the specified time unit. Defaults to 50000.
        time_unit (str, optional): The time unit used in the simulation. Defaults to "minutes".
        random_seed (int, optional): The random seed for reproducibility. Defaults to 123456.
        run (int, optional): The run number of the simulation. Defaults to 1.

    Returns:
        dict: A dictionary containing the simulation results including aggregate statistics.
    """
    # ------------------------------------------------------------
    cnv_hr_to_mins = 60

    # Generator which creates EV's
    class EV_Generator(sim.Component):
        # setup method is called when the component is created
        # and is used to initialize the component
        # switch off monitoring for mode and status
        def setup(self):
            self.mode.monitor(False)
            self.status.monitor(False)

        def process(self):
            while True:
                EV()
                iat = inter_arr_time_distr.sample()
                if fixed_utilization:
                    iat = iat/number_of_EVSE
                self.hold(iat)

    class EV(sim.Component):
        def setup(self):
            self.mode.monitor(False)
            self.status.monitor(False)

        def process(self):
            self.enter(waitingline)
            for EVSE in facility:
                if EVSE.ispassive():
                    EVSE.activate()
                    break  # activate at most one charging station
            self.passivate()

    class EVSE(sim.Component):
        def setup(self):
            self.mode.monitor(False)
            self.status.monitor(False)

            self.length = sim.Monitor(
                name="length", monitor=True, level=True, type="int32"
            )
            self.length_of_stay = sim.Monitor(
                name="length_of_stay", monitor=True, level=False, type="float"
            )
            self.power_mon = sim.Monitor(
                name="power.", monitor=True, level=True, type="float"
            )
            self.power = 1.0

        def process(self):
            while True:
                self.length.tally(0)
                while len(waitingline) == 0:
                    self.set_mode("Waiting")
                    self.passivate()
                self.car = waitingline.pop()
                self.length.tally(1)
                # wf = app.now()
                energy_request = energy_request_distr.sample()
                charging_time = energy_request / self.power
                # monEVSE_IDLE.tally(wf - ws)
                self.length_of_stay.tally(charging_time)
                self.power_mon.tally(self.power)
                self.set_mode("Charging")
                self.hold(charging_time)
                self.car.activate()

    # ------------------------------------------------------------
    # https://www.salabim.org/manual/Reference.html#environment
    app = sim.App(
        trace=False,  # defines whether to trace or not
        random_seed=random_seed,  # if “*”, a purely random value (based on the current time)
        time_unit=time_unit,  # defines the time unit used in the simulation
        name="Charging Station",  # name of the simulation
        do_reset=True,  # defines whether to reset the simulation when the run method is called
        yieldless=True,  # defines whether the simulation is yieldless or not
    )

    # Instantiate and activate the client generator
    EV_Generator(name="Electric Vehicles Generator")

    # Create Queue and set monitor to stats_only
    # https://www.salabim.org/manual/Queue.html
    waitingline = sim.Queue(name="Waiting EV's", monitor=True)
    # waitingline.length_of_stay.monitor(value=True)
    waitingline.length.reset_monitors(stats_only=True)
    waitingline.length_of_stay.reset_monitors(stats_only=True)

    # Instantiate the EVSE's, list comprehension
    facility = [EVSE() for _ in range(number_of_EVSE)]

    # Execute Simulation
    app.run(till=sim_time)

    # Calculate aggregate statistics
    total_evse_stay = sum(x.length_of_stay for x in facility).mean()
    total_evse_lngt = sum(x.length for x in facility).mean()

    # waitingline.mode.print_histogram(values=True)


    lmbda = cnv_hr_to_mins/inter_arr_time_distr.mean()
    if fixed_utilization:
        lmbda = lmbda*number_of_EVSE

    # Return results
    return {
        "run": run,
        "lambda": lmbda,
        "mu": cnv_hr_to_mins/energy_request_distr.mean(),
        "c": number_of_EVSE,
        "RO": total_evse_lngt / number_of_EVSE,
        "P0": 0,
        "Lq": waitingline.length.mean(),
        "Wq": waitingline.length_of_stay.mean(),
        "Ls": total_evse_lngt + waitingline.length.mean(),
        "Ws": total_evse_stay + waitingline.length_of_stay.mean(),
    }
