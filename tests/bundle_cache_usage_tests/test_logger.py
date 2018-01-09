# coding: latin-1
#
# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank_test.tank_test_base import setUpModule

import os
import time
from mock import patch

from sgtk.descriptor.bundle_cache_usage.logger import BundleCacheUsageLogger
from sgtk.descriptor.bundle_cache_usage.errors import (
    BundleCacheUsageTimeoutError,
    BundleCacheUsageInvalidBundleCacheRootError
)

from .test_base import TestBundleCacheUsageBase


class TestBundleCacheUsageLogger(TestBundleCacheUsageBase):
    """
    Tests the 'BundleCacheUsageLogger' class
    """

    def setUp(self):
        super(TestBundleCacheUsageLogger, self).setUp()
        BundleCacheUsageLogger.delete_instance()
        self._logger = BundleCacheUsageLogger()
        self._logger.start()

    def test_create_delete_instance(self):
        """
        Test for possible lock-ups by measuring elaped time
        for each individual create/destroy attemps
        """

        for count in range(0, self.DEFAULT_LOOP_COUNT):
            start_time = time.time()
            BundleCacheUsageLogger()
            BundleCacheUsageLogger.delete_instance()
            elapsed_time = time.time() - start_time
            # Should pretty much be instant
            self.assertLess(elapsed_time,
                            self.WAIT_TIME_INSTANT,
                            "Lock up detected")

    def test_delete_instance(self):
        """
        Test that deleting_instance() method can be called multiple times
        """

        for count in range(0, self.DEFAULT_LOOP_COUNT):
            start_time = time.time()

            BundleCacheUsageLogger()
            BundleCacheUsageLogger.delete_instance()
            BundleCacheUsageLogger.delete_instance()
            BundleCacheUsageLogger.delete_instance()
            BundleCacheUsageLogger()
            BundleCacheUsageLogger.delete_instance()
            BundleCacheUsageLogger.delete_instance()
            elapsed_time = time.time() - start_time
            # Should pretty much be instant
            self.assertLess(elapsed_time, self.WAIT_TIME_INSTANT, "Lock up detected")

    def test_stress_simple_start_stop(self):
        """
        Simple stress-Test for possible lock-ups while starting and stopping the
        worker thread.

        The test measures elaped time for each individual iteration and expect
        a near-instantaneous execution.
        """
        for count in range(0, self.DEFAULT_LOOP_COUNT):
            start_time = time.time()
            logger = BundleCacheUsageLogger()
            logger.start()
            BundleCacheUsageLogger.delete_instance()
            logger = None
            elapsed_time = time.time() - start_time
            # Should pretty much be instant
            self.assertLess(elapsed_time, self.WAIT_TIME_INSTANT, "Lock up detected")

    def test_stress_wait_worker_created_db(self):
        """
        Stress-Testing that a connection is ready after `start` is called.
        """

        # Need override setUp() and start the test with
        # instance and db file deleted.
        BundleCacheUsageLogger.delete_instance()
        self.delete_db()

        for count in range(0, self.DEFAULT_LOOP_COUNT/4):
            self.assertFalse(os.path.exists(self.expected_db_path))
            logger = BundleCacheUsageLogger()
            logger.start()
            logger.log_usage("bogus")

            # Wait for either timeout or database created
            start_time = time.time()
            while(True):
                if os.path.exists(self.expected_db_path):
                    break

                elapsed_time = time.time() - start_time
                if  elapsed_time > self.WAIT_TIME_SHORT:
                    # Should pretty quick
                    self.fail("Timeout waiting for database creation.")

                time.sleep(0.01)  # allow worker processing

            # Reset & delete for next iteration
            logger.delete_instance()
            os.remove(self.expected_db_path)

    def test_stress_start_stop_with_operations(self):
        """
        Stress-Test for possible lock-ups starting, issuing some operations and then
        and stopping the worker.

        The test measures elapsed time for each individual iteration and expect
        a near-instantaneous execution.
        """

        OPERATION_COUNT = 3
        for count in range(0, self.DEFAULT_LOOP_COUNT):
            start_time = time.time()
            logger = BundleCacheUsageLogger()
            logger.start()
            for _ in range(0, OPERATION_COUNT):
                logger.log_usage(self._test_bundle_path)
            BundleCacheUsageLogger.delete_instance()
            elapsed_time = time.time() - start_time
            self.assertEquals(
                logger.completed_count, OPERATION_COUNT,
                "Was expecting all tasks to be completed after `stop()`"
            )
            self.assertEquals(
                logger.pending_count, 0,
                "Was not expecting pending tasks after `stop()`."
            )
            # Should be quick, only a few db operation for each loop iteration
            self.assertLess(elapsed_time, self.WAIT_TIME_MEDIUM, "Lock up possibly detected")

    def test_main_loop_wait(self):
        """
        Tests join/waiting for worker thread termintation.
        We queue a task that takes longer than default wait
        time to check for raised exception
        """

        LONG_TASK_SLEEP_TIME = 4.0
        # Queue the long task.
        self._logger._queue_task(time.sleep, LONG_TASK_SLEEP_TIME)

        with self.assertRaises(BundleCacheUsageTimeoutError):
            self._logger.stop(LONG_TASK_SLEEP_TIME / 2)

    def test_queue_task(self):
        """
        Tests submitting a bulk of simple & very short wait tasks and verify
        that all tasks have been executed and completed before the ending 'stop'
        method times out.
        """
        for count in range(0, self.DEFAULT_LOOP_COUNT):
            self._logger._queue_task(time.sleep, 0.01)

        self.assertGreater(
            self._logger.pending_count,
            0,
            "Was expecting some incomplete tasks."
        )
        self._logger.stop(self.WAIT_TIME_MEGA_LONG)
        self.assertEquals(
            self._logger.completed_count,
            self.DEFAULT_LOOP_COUNT,
            "Was expecting all tasks to be completed after `stop()`"
        )
        self.assertEquals(
            self._logger.pending_count,
            0,
            "Was not expecting pending tasks after `stop()`."
        )

    def test_queue_task_timing_out(self):
        """
        Tests submitting a bulk of simple & very short wait tasks and verify
        that we're able to exit due a timeout with some uncompleted tasks.
        """
        TIMEOUT = 2.0

        for count in range(0, self.DEFAULT_LOOP_COUNT):
            self._logger._queue_task(time.sleep, 0.01)

        self.assertGreater(self._logger.pending_count, 0, "Was expecting some incomplete tasks.")

        # Forcing a shorter timeout
        # The timeout below is way shorter than 1000 * 0.01s = 10 seconds
        start_time = time.time()
        with self.assertRaises(BundleCacheUsageTimeoutError):
            self._logger.stop(TIMEOUT)
        elapsed_time = time.time() - start_time

        # Verify that the timeout is approx. TIMEOUT seconds
        self.assertIsWithinPct(elapsed_time, TIMEOUT, 5)

        # Verify that we do have pending tasks
        self.assertGreater(self._logger.pending_count, 0,
                           "We're expecting a worker timeout, there should be incompleted tasks.")

        # finish waiting, we know that those tasks will take longer than 2 seconds
        try:
            self._logger.delete_instance()
        except BundleCacheUsageTimeoutError:
            pass

    def test_queue_log_usage(self):
        """
        Tests performances of tracking a large number of descriptor through usage of the logger class.
        Since actual database accesses are done asynchronously logging usage on the main thread should
        be rather quick, completion of all of the database commits should be substantially longer.

        There should be at the very least a 10:1 ratio
        Development system was showing approximately � 36:0
        """

        MINIMAL_EXPECTED_RATIO = 20

        start_time = time.time()
        for count in range(0, self.DEFAULT_LOOP_COUNT):
            self._logger.log_usage(self._test_bundle_path)

        queuing_time = time.time() - start_time
        try:
            self._logger.stop(self.WAIT_TIME_MEGA_LONG)
        except BundleCacheUsageTimeoutError:
            self._logger.stop(self.WAIT_TIME_MEGA_LONG)

        completing_all_tasks_time = time.time() - start_time
        self.assertEquals(
            self._logger.pending_count,
            0,
            "Was not expecting pending tasks after `stop`."
        )

        print("\n%s: queuing_time             : %5.3fs" % (self._testMethodName, queuing_time))
        print("%s: completing_all_tasks_time: %4.1fs" % (self._testMethodName, completing_all_tasks_time))
        if queuing_time > 0:
            ratio = completing_all_tasks_time / queuing_time
            print("%s: ratio                    : %4.1fX" % (self._testMethodName, ratio))
            self.assertGreater(
                ratio,
                MINIMAL_EXPECTED_RATIO,
                "Expecting at the very least a %d:1 radio between completing tasks and queuing them" % (
                    MINIMAL_EXPECTED_RATIO
                )
            )

    def helper_divide_a_by_b(self, a, b):
        """
        Helper method used by the following test(s):
        - test_indirect_error_reporting_from_worker_thread

        :param a: an int arithmetic dividend
        :param b: an int arithmetic divisor
        :return: an int result quotient
        """
        return a / b

    def test_indirect_error_reporting_from_worker_thread(self):
        """
        Indirectly exercise the error/exception reporting from worker
        thread through usage of the 'log_usage' method through worker thread.

        Reference:
            http://cpython-test-docs.readthedocs.io/en/latest/library/unittest.mock.html
        """

        with patch("logging.Logger.error") as mocked_log_error:
            # Queue non-problematic tasks
            self._logger._queue_task(self.helper_divide_a_by_b, 10, 1)
            time.sleep(self.WORKER_PROCESSING_TIME) # allow worker processing
            self._logger.log_usage(self._test_bundle_path)
            time.sleep(self.WORKER_PROCESSING_TIME)  # allow worker processing
            self.assertEquals(0, mocked_log_error.call_count)

            # Queue a task that will generate an exception
            self._logger._queue_task(self.helper_divide_a_by_b, 10, 0)
            time.sleep(self.WORKER_PROCESSING_TIME)  # allow worker processing
            self._logger.log_usage(self._test_bundle_path)
            time.sleep(self.WORKER_PROCESSING_TIME)  # allow worker processing
            self.assertEquals(1, mocked_log_error.call_count)

            # Again, but now with several errors
            mocked_log_error.reset_mock()
            self._logger._queue_task(self.helper_divide_a_by_b, 10, 0)
            self._logger._queue_task(self.helper_divide_a_by_b, 10, 0)
            self._logger._queue_task(self.helper_divide_a_by_b, 10, 0)
            time.sleep(self.WORKER_PROCESSING_TIME)  # allow worker processing
            self._logger.log_usage(self._test_bundle_path)
            time.sleep(self.WORKER_PROCESSING_TIME)  # allow worker processing
            self.assertEquals(3, mocked_log_error.call_count)

    def test_indirect_database_error_reporting_from_worker_thread(self):
        """
        Indirectly tests the database error/exception reporting from worker
        thread through usage of the 'log_usage' method.
        """
        # For this test, we have to override what's being done in setUp()
        # and start with a non-existing db file and no existing instance.
        self.delete_db()

        with patch("logging.Logger.error") as mocked_log_error:
            with patch(
                "sgtk.descriptor.bundle_cache_usage.database.BundleCacheUsageDatabase._create_main_table"
            ) as mocked_create_main_table:

                # Mocking 'BundleCacheUsageDatabase._create_main_table'
                # prevents creation of the main table and cause pretty
                # much all writes to fail.
                logger = BundleCacheUsageLogger()
                logger.start()
                time.sleep(self.WORKER_PROCESSING_TIME)  # allow worker processing
                self.assertEquals(0, mocked_create_main_table.call_count)

                # With database NOT having a main table
                # let's try logging some usage.
                logger.log_usage(self._test_bundle_path)
                time.sleep(self.WORKER_PROCESSING_TIME)  # allow worker processing
                self.assertEquals(1, mocked_create_main_table.call_count)

                # Now, the next call to 'log_usage' should trigger
                # splitting out the errors
                logger.log_usage(self._test_bundle_path)
                self.assertEquals(1, mocked_log_error.call_count)
                self.assertEquals(
                    "Unexpected error consuming task : no such table: bundles",
                    mocked_log_error.call_args_list[0][0][0]
                )

    def test_indirect_time_override_error_reporting_from_worker_thread(self):
        """
        Indirectly tests the database error/exception reporting from worker
        thread through usage of the 'log_usage' method through worker thread.
        """

        with patch("logging.Logger.error") as mocked_log_error:
            # Mocking 'BundleCacheUsageDatabase._create_main_table'
            # prevents creation of the main table and cause pretty
            # much all writes to fail.
            logger = BundleCacheUsageLogger()
            logger.start()

            BAD_TIME_STRING = "asgjdhasgjhdasd"

            # Assign an invalid timestamp
            os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE"] = BAD_TIME_STRING

            # With database NOT having a main table
            # let's try logging some usage.
            logger.log_usage(self._test_bundle_path)
            time.sleep(self.WORKER_PROCESSING_TIME)  # allow worker processing

            # Now, the next call to 'log_usage' should trigger
            # splitting out the errors
            logger.log_usage(self._test_bundle_path)
            self.assertEquals(1, mocked_log_error.call_count)
            self.assertEquals(
                "Unexpected error consuming task : invalid literal for int() with base 10: '%s'" % BAD_TIME_STRING,
                mocked_log_error.call_args_list[0][0][0]
            )

    def test_singleton(self):
        """ Tests that multiple instantiations return the same object."""
        db1 = BundleCacheUsageLogger()
        db2 = BundleCacheUsageLogger()
        db3 = BundleCacheUsageLogger()
        self.assertTrue(db1 == db2 == db3)
