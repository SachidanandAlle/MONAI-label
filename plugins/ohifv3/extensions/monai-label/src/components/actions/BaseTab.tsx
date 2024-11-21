import { Component } from 'react';
import PropTypes from 'prop-types';

import './BaseTab.css';
import { UIModalService, UINotificationService } from '@ohif/core';
import { currentSegmentsInfo } from '../../utils/SegUtils';

export default class BaseTab extends Component {
  static propTypes = {
    tabIndex: PropTypes.number,
    info: PropTypes.any,
    segmentId: PropTypes.string,
    viewConstants: PropTypes.any,
    client: PropTypes.func,
    updateView: PropTypes.func,
    onSelectActionTab: PropTypes.func,
    onOptionsConfig: PropTypes.func,
  };

  notification: any;
  uiModelService: any;
  tabId: string;

  constructor(props) {
    super(props);
    this.notification = new UINotificationService();
    this.uiModelService = new UIModalService();
    this.tabId = 'tab-' + this.props.tabIndex;
  }

  onSelectActionTab = (evt) => {
    this.props.onSelectActionTab(evt.currentTarget.value);
  };
  onEnterActionTab = () => {};
  onLeaveActionTab = () => {};
  onSegmentCreated = (id) => {};
  onSegmentUpdated = (id) => {};
  onSegmentDeleted = (id) => {};
  onSegmentSelected = (id) => {};
  onSelectModel = (model) => {};

  segmentInfo = () => {
    return currentSegmentsInfo(
      this.props.servicesManager.services.segmentationService
    ).info;
  };
}
